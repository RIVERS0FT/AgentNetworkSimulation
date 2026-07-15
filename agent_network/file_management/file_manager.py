from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
import stat
import threading
import uuid
import zipfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Dict, Iterable, List, Mapping, Optional, Sequence

from .models import DownloadDescriptor, FileResource


class FileManagerError(RuntimeError):
    """Base error for managed file operations."""


class ResourceNotFoundError(FileManagerError):
    pass


class ResourceNotReadyError(FileManagerError):
    pass


class UnsafePathError(FileManagerError):
    pass


class ArchiveLimitError(FileManagerError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FileManager:
    """Unified managed-file infrastructure.

    Business modules own file semantics. This class owns safe locations, atomic writes,
    reads, archives, visibility metadata, downloads, integrity metadata and deletion.
    """

    CATALOG_VERSION = "file-registry.v1"

    def __init__(
        self,
        roots: Mapping[str, str | os.PathLike[str]],
        *,
        catalog_path: str | os.PathLike[str],
    ) -> None:
        if not roots:
            raise ValueError("at least one managed root is required")
        self._roots: Dict[str, Path] = {
            name: Path(path).resolve() for name, path in roots.items()
        }
        for name, root in self._roots.items():
            if not name or Path(name).name != name:
                raise ValueError(f"invalid root name: {name!r}")
            root.mkdir(parents=True, exist_ok=True)
        self._catalog_path = Path(catalog_path).resolve()
        self._catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._resources: Dict[str, FileResource] = {}
        self._load_catalog()

    def _load_catalog(self) -> None:
        if not self._catalog_path.is_file():
            return
        try:
            raw = json.loads(self._catalog_path.read_text(encoding="utf-8"))
            if raw.get("version") != self.CATALOG_VERSION:
                raise FileManagerError("unsupported file registry version")
            resources = raw.get("resources", [])
            self._resources = {
                item["resource_id"]: FileResource.from_dict(item)
                for item in resources
            }
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise FileManagerError(f"invalid file registry: {exc}") from exc

    def _save_catalog(self) -> None:
        payload = {
            "version": self.CATALOG_VERSION,
            "resources": [
                item.to_dict()
                for item in sorted(
                    self._resources.values(), key=lambda value: value.resource_id
                )
            ],
        }
        temp_path = self._catalog_path.with_name(
            f".{self._catalog_path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_path, self._catalog_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _root(self, root_name: str) -> Path:
        try:
            return self._roots[root_name]
        except KeyError as exc:
            raise ValueError(f"unknown managed root: {root_name!r}") from exc

    def resolve_path(self, root_name: str, relative_path: str) -> Path:
        if not relative_path:
            raise UnsafePathError("relative path is required")
        raw = Path(relative_path)
        if raw.is_absolute() or ".." in raw.parts:
            raise UnsafePathError("path must be relative and must not contain '..'")
        root = self._root(root_name)
        resolved = (root / raw).resolve()
        if resolved != root and root not in resolved.parents:
            raise UnsafePathError("path escapes managed root")
        return resolved

    def _resource(self, resource_id: str) -> FileResource:
        try:
            return self._resources[resource_id]
        except KeyError as exc:
            raise ResourceNotFoundError(f"resource '{resource_id}' not found") from exc

    def get_resource(self, resource_id: str) -> FileResource:
        with self._lock:
            return self._resource(resource_id)

    def list_resources(
        self,
        *,
        owner_type: Optional[str] = None,
        owner_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        include_hidden: bool = False,
        include_deleted: bool = False,
    ) -> List[FileResource]:
        with self._lock:
            resources = list(self._resources.values())
        result = []
        for resource in resources:
            if owner_type and resource.owner_type != owner_type:
                continue
            if owner_id and resource.owner_id != owner_id:
                continue
            if resource_type and resource.resource_type != resource_type:
                continue
            if not include_hidden and not resource.visible:
                continue
            if not include_deleted and resource.state == "deleted":
                continue
            result.append(resource)
        return sorted(result, key=lambda value: (value.created_at, value.resource_id))

    def register_existing(
        self,
        *,
        owner_type: str,
        owner_id: str,
        resource_type: str,
        root_name: str,
        relative_path: str,
        logical_name: str = "",
        media_type: str = "",
        visible: bool = True,
        resource_id: str = "",
    ) -> FileResource:
        path = self.resolve_path(root_name, relative_path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        if path.is_symlink():
            raise UnsafePathError("symbolic links cannot be registered")
        now = _utc_now()
        resource = FileResource(
            resource_id=resource_id or f"file_{uuid.uuid4().hex}",
            owner_type=owner_type,
            owner_id=owner_id,
            resource_type=resource_type,
            root_name=root_name,
            relative_path=Path(relative_path).as_posix(),
            logical_name=logical_name or path.name,
            media_type=media_type
            or mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
            visible=bool(visible),
            state="ready",
            size_bytes=self._path_size(path),
            sha256="" if path.is_dir() else _sha256_file(path),
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            if resource.resource_id in self._resources:
                raise ValueError(f"resource '{resource.resource_id}' already exists")
            self._resources[resource.resource_id] = resource
            self._save_catalog()
        return resource

    def write_bytes(
        self,
        data: bytes,
        *,
        owner_type: str,
        owner_id: str,
        resource_type: str,
        root_name: str,
        relative_path: str,
        logical_name: str = "",
        media_type: str = "application/octet-stream",
        visible: bool = True,
        resource_id: str = "",
        overwrite: bool = False,
    ) -> FileResource:
        path = self.resolve_path(root_name, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not overwrite:
            raise FileExistsError(str(path))
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_bytes(data)
            os.replace(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
        return self._upsert_written_resource(
            path=path,
            owner_type=owner_type,
            owner_id=owner_id,
            resource_type=resource_type,
            root_name=root_name,
            relative_path=relative_path,
            logical_name=logical_name,
            media_type=media_type,
            visible=visible,
            resource_id=resource_id,
        )

    def write_text(
        self, text: str, *, encoding: str = "utf-8", **kwargs
    ) -> FileResource:
        return self.write_bytes(text.encode(encoding), **kwargs)

    def _upsert_written_resource(
        self,
        *,
        path: Path,
        owner_type: str,
        owner_id: str,
        resource_type: str,
        root_name: str,
        relative_path: str,
        logical_name: str,
        media_type: str,
        visible: bool,
        resource_id: str,
    ) -> FileResource:
        now = _utc_now()
        with self._lock:
            existing = self._resources.get(resource_id) if resource_id else None
            resolved_id = resource_id or f"file_{uuid.uuid4().hex}"
            resource = FileResource(
                resource_id=resolved_id,
                owner_type=owner_type,
                owner_id=owner_id,
                resource_type=resource_type,
                root_name=root_name,
                relative_path=Path(relative_path).as_posix(),
                logical_name=logical_name or path.name,
                media_type=media_type
                or mimetypes.guess_type(path.name)[0]
                or "application/octet-stream",
                visible=bool(visible),
                state="ready",
                size_bytes=path.stat().st_size,
                sha256=_sha256_file(path),
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
            self._resources[resolved_id] = resource
            self._save_catalog()
            return resource

    def append_text(
        self,
        resource_id: str,
        text: str,
        *,
        encoding: str = "utf-8",
    ) -> FileResource:
        with self._lock:
            resource = self._resource(resource_id)
            if resource.state != "ready":
                raise ResourceNotReadyError(resource_id)
            path = self.resolve_path(resource.root_name, resource.relative_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding=encoding) as stream:
                stream.write(text)
                stream.flush()
            updated = replace(
                resource,
                size_bytes=path.stat().st_size,
                sha256=_sha256_file(path),
                updated_at=_utc_now(),
                error_message="",
            )
            self._resources[resource_id] = updated
            self._save_catalog()
            return updated

    def read_bytes(self, resource_id: str, *, allow_hidden: bool = False) -> bytes:
        resource = self._assert_readable(resource_id, allow_hidden=allow_hidden)
        path = self.resolve_path(resource.root_name, resource.relative_path)
        if not path.is_file():
            raise ResourceNotReadyError(f"resource '{resource_id}' is not a file")
        return path.read_bytes()

    def read_text(
        self,
        resource_id: str,
        *,
        encoding: str = "utf-8",
        allow_hidden: bool = False,
    ) -> str:
        return self.read_bytes(resource_id, allow_hidden=allow_hidden).decode(encoding)

    def open_stream(
        self, resource_id: str, *, allow_hidden: bool = False
    ) -> BinaryIO:
        resource = self._assert_readable(resource_id, allow_hidden=allow_hidden)
        path = self.resolve_path(resource.root_name, resource.relative_path)
        if not path.is_file():
            raise ResourceNotReadyError(f"resource '{resource_id}' is not a file")
        return path.open("rb")

    def _assert_readable(self, resource_id: str, *, allow_hidden: bool) -> FileResource:
        with self._lock:
            resource = self._resource(resource_id)
        if resource.state != "ready":
            raise ResourceNotReadyError(
                f"resource '{resource_id}' is not ready: {resource.state}"
            )
        if not allow_hidden and not resource.visible:
            raise ResourceNotReadyError(f"resource '{resource_id}' is hidden")
        path = self.resolve_path(resource.root_name, resource.relative_path)
        if not path.exists():
            raise ResourceNotFoundError(f"resource file missing: {resource_id}")
        return resource

    def set_visibility(
        self, resource_ids: Iterable[str], visible: bool
    ) -> List[FileResource]:
        updated = []
        with self._lock:
            for resource_id in resource_ids:
                resource = self._resource(resource_id)
                if resource.state == "deleted":
                    raise ResourceNotReadyError(f"resource '{resource_id}' is deleted")
                value = replace(
                    resource,
                    visible=bool(visible),
                    updated_at=_utc_now(),
                )
                self._resources[resource_id] = value
                updated.append(value)
            self._save_catalog()
        return updated

    def prepare_download(
        self, resource_id: str, *, allow_hidden: bool = False
    ) -> DownloadDescriptor:
        resource = self._assert_readable(resource_id, allow_hidden=allow_hidden)
        path = self.resolve_path(resource.root_name, resource.relative_path)
        if not path.is_file():
            raise ResourceNotReadyError("directories must be archived before download")
        current_sha = _sha256_file(path)
        if resource.sha256 and current_sha != resource.sha256:
            raise FileManagerError(
                f"resource '{resource_id}' failed SHA-256 validation"
            )
        return DownloadDescriptor(
            resource_id=resource.resource_id,
            logical_name=resource.logical_name,
            media_type=resource.media_type,
            size_bytes=path.stat().st_size,
            sha256=current_sha,
            internal_path=str(path),
        )

    def create_archive(
        self,
        resource_ids: Sequence[str],
        *,
        owner_type: str,
        owner_id: str,
        root_name: str,
        relative_path: str,
        logical_name: str = "",
        visible: bool = True,
        resource_id: str = "",
    ) -> FileResource:
        if not resource_ids:
            raise ValueError("at least one resource is required")
        destination = self.resolve_path(root_name, relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(str(destination))
        temp_path = destination.with_name(
            f".{destination.name}.{uuid.uuid4().hex}.tmp"
        )
        archive_names: set[str] = set()
        try:
            with zipfile.ZipFile(temp_path, "w") as archive:
                source_resources = (
                    self._assert_readable(item, allow_hidden=True)
                    for item in resource_ids
                )
                for source_resource in source_resources:
                    source = self.resolve_path(
                        source_resource.root_name,
                        source_resource.relative_path,
                    )
                    base_name = source_resource.logical_name or source.name
                    if source.is_dir():
                        for child in sorted(source.rglob("*")):
                            if child.is_symlink() or not child.is_file():
                                continue
                            relative = Path(base_name) / child.relative_to(source)
                            archive_name = self._unique_archive_name(
                                relative.as_posix(), archive_names
                            )
                            archive.write(
                                child,
                                archive_name,
                                compress_type=self._compression_for(child),
                            )
                    else:
                        archive_name = self._unique_archive_name(
                            base_name, archive_names
                        )
                        archive.write(
                            source,
                            archive_name,
                            compress_type=self._compression_for(source),
                        )
            os.replace(temp_path, destination)
        finally:
            if temp_path.exists():
                temp_path.unlink()
        return self._upsert_written_resource(
            path=destination,
            owner_type=owner_type,
            owner_id=owner_id,
            resource_type="archive",
            root_name=root_name,
            relative_path=relative_path,
            logical_name=logical_name or destination.name,
            media_type="application/zip",
            visible=visible,
            resource_id=resource_id,
        )

    @staticmethod
    def _compression_for(path: Path) -> int:
        return (
            zipfile.ZIP_STORED
            if path.suffix.lower() == ".pcap"
            else zipfile.ZIP_DEFLATED
        )

    @staticmethod
    def _unique_archive_name(name: str, used: set[str]) -> str:
        candidate = Path(name).as_posix().lstrip("/")
        if (
            not candidate
            or candidate in {".", ".."}
            or ".." in Path(candidate).parts
        ):
            raise UnsafePathError(f"unsafe archive entry: {name!r}")
        if candidate in used:
            raise FileManagerError(f"duplicate archive entry: {candidate}")
        used.add(candidate)
        return candidate

    def extract_archive(
        self,
        archive_resource_id: str,
        *,
        destination_root_name: str,
        destination_relative_dir: str,
        max_files: int = 10_000,
        max_total_bytes: int = 2 * 1024 * 1024 * 1024,
        max_file_bytes: int = 512 * 1024 * 1024,
    ) -> Path:
        archive_resource = self._assert_readable(
            archive_resource_id, allow_hidden=True
        )
        archive_path = self.resolve_path(
            archive_resource.root_name, archive_resource.relative_path
        )
        destination = self.resolve_path(
            destination_root_name, destination_relative_dir
        )
        if destination.exists():
            raise FileExistsError(str(destination))
        temp_dir = destination.with_name(
            f".{destination.name}.{uuid.uuid4().hex}.extracting"
        )
        total_bytes = 0
        try:
            temp_dir.mkdir(parents=True)
            with zipfile.ZipFile(archive_path, "r") as archive:
                members = archive.infolist()
                if len(members) > max_files:
                    raise ArchiveLimitError("archive contains too many entries")
                for member in members:
                    member_path = Path(member.filename)
                    if (
                        member_path.is_absolute()
                        or ".." in member_path.parts
                        or self._zip_member_is_symlink(member)
                    ):
                        raise UnsafePathError(
                            f"unsafe archive entry: {member.filename!r}"
                        )
                    if member.file_size > max_file_bytes:
                        raise ArchiveLimitError(
                            f"archive entry too large: {member.filename}"
                        )
                    total_bytes += member.file_size
                    if total_bytes > max_total_bytes:
                        raise ArchiveLimitError(
                            "archive exceeds total extraction limit"
                        )
                    target = (temp_dir / member_path).resolve()
                    if target != temp_dir and temp_dir not in target.parents:
                        raise UnsafePathError(
                            "archive entry escapes destination: "
                            f"{member.filename!r}"
                        )
                    if member.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member, "r") as source, target.open(
                        "wb"
                    ) as sink:
                        shutil.copyfileobj(source, sink)
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp_dir, destination)
            return destination
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    @staticmethod
    def _zip_member_is_symlink(member: zipfile.ZipInfo) -> bool:
        mode = member.external_attr >> 16
        return stat.S_ISLNK(mode)

    def delete(self, resource_ids: Iterable[str]) -> List[FileResource]:
        deleted = []
        with self._lock:
            for resource_id in resource_ids:
                resource = self._resource(resource_id)
                path = self.resolve_path(
                    resource.root_name, resource.relative_path
                )
                if path.is_symlink():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
                updated = replace(
                    resource,
                    state="deleted",
                    size_bytes=0,
                    sha256="",
                    visible=False,
                    updated_at=_utc_now(),
                )
                self._resources[resource_id] = updated
                deleted.append(updated)
            self._save_catalog()
        return deleted

    @staticmethod
    def _path_size(path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        return sum(
            item.stat().st_size for item in path.rglob("*") if item.is_file()
        )
