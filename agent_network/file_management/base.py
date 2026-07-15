from __future__ import annotations
import hashlib
import json
import mimetypes
import os
import re
import threading
import uuid
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, Optional
try:
    import fcntl
except ImportError:
    fcntl = None
from .models import FileResource

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
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def stable_resource_id(*parts: str) -> str:
    normalized = '_'.join((str(part or '').strip() for part in parts))
    safe = re.sub('[^A-Za-z0-9_.-]+', '_', normalized).strip('_.-')
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:12]
    return f"{safe[:96] or 'resource'}_{digest}"

class ResourceCatalog:
    CATALOG_VERSION = 'file-registry.v1'

    def __init__(self, roots: Mapping[str, str | os.PathLike[str]], *, catalog_path: str | os.PathLike[str]) -> None:
        if not roots:
            raise ValueError('at least one managed root is required')
        self._roots: Dict[str, Path] = {name: Path(path).resolve() for name, path in roots.items()}
        for name, root in self._roots.items():
            if not name or Path(name).name != name:
                raise ValueError(f'invalid root name: {name!r}')
            root.mkdir(parents=True, exist_ok=True)
        self._catalog_path = Path(catalog_path).resolve()
        self._catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self._catalog_lock_path = self._catalog_path.with_suffix(self._catalog_path.suffix + '.lock')
        self._thread_lock = threading.RLock()
        self._resources: Dict[str, FileResource] = {}
        with self._catalog_guard(write=False):
            pass

    @contextmanager
    def _catalog_guard(self, *, write: bool) -> Iterator[None]:
        with self._thread_lock:
            self._catalog_lock_path.parent.mkdir(parents=True, exist_ok=True)
            with self._catalog_lock_path.open('a+b') as lock_stream:
                if fcntl is not None:
                    fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
                try:
                    self._load_catalog_unlocked()
                    yield
                    if write:
                        self._save_catalog_unlocked()
                finally:
                    if fcntl is not None:
                        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)

    def _load_catalog_unlocked(self) -> None:
        if not self._catalog_path.is_file():
            self._resources = {}
            return
        try:
            raw = json.loads(self._catalog_path.read_text(encoding='utf-8'))
            if raw.get('version') != self.CATALOG_VERSION:
                raise FileManagerError('unsupported file registry version')
            resources = raw.get('resources', [])
            self._resources = {item['resource_id']: FileResource.from_dict(item) for item in resources}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise FileManagerError(f'invalid file registry: {exc}') from exc

    def _save_catalog_unlocked(self) -> None:
        payload = {'version': self.CATALOG_VERSION, 'resources': [item.to_dict() for item in sorted(self._resources.values(), key=lambda value: value.resource_id)]}
        temp_path = self._catalog_path.with_name(f'.{self._catalog_path.name}.{uuid.uuid4().hex}.tmp')
        try:
            temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temp_path, self._catalog_path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _root(self, root_name: str) -> Path:
        try:
            return self._roots[root_name]
        except KeyError as exc:
            raise ValueError(f'unknown managed root: {root_name!r}') from exc

    def root_path(self, root_name: str) -> Path:
        return self._root(root_name)

    def resolve_path(self, root_name: str, relative_path: str) -> Path:
        if not relative_path:
            raise UnsafePathError('relative path is required')
        raw = Path(relative_path)
        if raw.is_absolute() or '..' in raw.parts:
            raise UnsafePathError("path must be relative and must not contain '..'")
        root = self._root(root_name)
        resolved = (root / raw).resolve()
        if resolved != root and root not in resolved.parents:
            raise UnsafePathError('path escapes managed root')
        return resolved

    def _resource_unlocked(self, resource_id: str) -> FileResource:
        try:
            return self._resources[resource_id]
        except KeyError as exc:
            raise ResourceNotFoundError(f"resource '{resource_id}' not found") from exc

    def get_resource(self, resource_id: str) -> FileResource:
        with self._catalog_guard(write=False):
            return self._resource_unlocked(resource_id)

    def find_resource(self, *, root_name: Optional[str]=None, relative_path: Optional[str]=None, owner_type: Optional[str]=None, owner_id: Optional[str]=None, resource_type: Optional[str]=None, logical_name: Optional[str]=None, include_deleted: bool=False) -> Optional[FileResource]:
        normalized_path = Path(relative_path).as_posix() if relative_path is not None else None
        with self._catalog_guard(write=False):
            for resource in self._resources.values():
                if not include_deleted and resource.state == 'deleted':
                    continue
                if root_name is not None and resource.root_name != root_name:
                    continue
                if normalized_path is not None and resource.relative_path != normalized_path:
                    continue
                if owner_type is not None and resource.owner_type != owner_type:
                    continue
                if owner_id is not None and resource.owner_id != owner_id:
                    continue
                if resource_type is not None and resource.resource_type != resource_type:
                    continue
                if logical_name is not None and resource.logical_name != logical_name:
                    continue
                return resource
        return None

    def list_resources(self, *, owner_type: Optional[str]=None, owner_id: Optional[str]=None, resource_type: Optional[str]=None, include_hidden: bool=False, include_deleted: bool=False) -> List[FileResource]:
        with self._catalog_guard(write=False):
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
            if not include_deleted and resource.state == 'deleted':
                continue
            result.append(resource)
        return sorted(result, key=lambda value: (value.created_at, value.resource_id))

    def register_existing(self, *, owner_type: str, owner_id: str, resource_type: str, root_name: str, relative_path: str, logical_name: str='', media_type: str='', visible: bool=True, resource_id: str='', upsert: bool=False) -> FileResource:
        path = self.resolve_path(root_name, relative_path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        if path.is_symlink():
            raise UnsafePathError('symbolic links cannot be registered')
        resolved_id = resource_id or stable_resource_id(owner_type, owner_id, resource_type, Path(relative_path).as_posix())
        now = _utc_now()
        with self._catalog_guard(write=True):
            existing = self._resources.get(resolved_id)
            if existing and not upsert:
                raise ValueError(f"resource '{resolved_id}' already exists")
            resource = FileResource(resource_id=resolved_id, owner_type=owner_type, owner_id=owner_id, resource_type=resource_type, root_name=root_name, relative_path=Path(relative_path).as_posix(), logical_name=logical_name or path.name, media_type=media_type or ('inode/directory' if path.is_dir() else mimetypes.guess_type(path.name)[0]) or 'application/octet-stream', visible=bool(visible), state='ready', size_bytes=self._path_size(path), sha256='' if path.is_dir() else _sha256_file(path), created_at=existing.created_at if existing else now, updated_at=now)
            self._resources[resolved_id] = resource
            return resource

    def refresh(self, resource_id: str, *, compute_sha256: bool=True) -> FileResource:
        with self._catalog_guard(write=True):
            resource = self._resource_unlocked(resource_id)
            path = self.resolve_path(resource.root_name, resource.relative_path)
            if not path.exists():
                updated = replace(resource, state='failed', error_message='physical file is missing', updated_at=_utc_now())
                self._resources[resource_id] = updated
                raise ResourceNotFoundError(f'resource file missing: {resource_id}')
            updated = replace(resource, state='ready', size_bytes=self._path_size(path), sha256='' if path.is_dir() else _sha256_file(path) if compute_sha256 else resource.sha256, updated_at=_utc_now(), error_message='')
            self._resources[resource_id] = updated
            return updated

    @staticmethod
    def _path_size(path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        return sum(item.stat().st_size for item in path.rglob('*') if item.is_file() and not item.is_symlink())
