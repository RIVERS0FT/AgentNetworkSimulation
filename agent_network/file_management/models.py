from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class FileResource:
    resource_id: str
    owner_type: str
    owner_id: str
    resource_type: str
    root_name: str
    relative_path: str
    logical_name: str
    media_type: str
    visible: bool
    state: str
    size_bytes: int
    sha256: str
    created_at: str
    updated_at: str
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "FileResource":
        return cls(**value)


@dataclass(frozen=True)
class DownloadDescriptor:
    resource_id: str
    logical_name: str
    media_type: str
    size_bytes: int
    sha256: str
    internal_path: str
