"""AgentNetwork log schemas, recording, querying and file management.

Application and system log behavior is provided by the internal base module.
The packet-oriented network.jsonl v4 contract is defined here and replaces the
legacy HTTP-oriented network event flow.
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from . import _log_manager_core as _core

# Re-export the existing application/system implementation and public helpers.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)


def _packet_timestamp(value: Any = "") -> str:
    """Return an RFC 3339 UTC timestamp with PCAP-friendly microseconds."""
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            parsed = datetime.now(timezone.utc)
    else:
        parsed = datetime.now(timezone.utc)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


NETWORK_CONTEXT_FIELDS = {
    "trace_id": {"type": "string"},
    "capture_id": {"type": "string"},
    "packet_index": {"type": "integer"},
    "observer_agent_id": {"type": "string"},
    "runtime_container": {"type": "string"},
    "interface": {"type": "string"},
    "captured_length": {"type": "integer"},
    "original_length": {"type": "integer"},
    "truncated": {"type": "boolean"},
}
NETWORK_RAW_FIELDS = {
    "format": {"type": "string"},
    "encoding": {"type": "string"},
    "data": {"type": "string"},
    "byte_length": {"type": "integer"},
    "packet_count": {"type": "integer"},
    "sha256": {"type": "string"},
}

NETWORK_EVENTS = frozenset({"packet"})
NETWORK_ALLOWED = ("context", "network", "raw")


def _network_fields() -> Dict[str, Any]:
    return {
        "timestamp": {"type": "string", "required": True},
        "log_id": {"type": "string", "required": True},
        "context": _object(
            properties=NETWORK_CONTEXT_FIELDS,
            required_properties=list(NETWORK_CONTEXT_FIELDS),
        ),
        # TShark packet["_source"]["layers"] is stored verbatim.
        "network": _object(),
        "raw": _object(
            properties=NETWORK_RAW_FIELDS,
            required_properties=list(NETWORK_RAW_FIELDS),
        ),
    }


network_log_schema.clear()
network_log_schema.update(
    {
        "name": "network.jsonl",
        "format": "jsonl",
        "log_type": "network",
        "schema_version": "network.v4",
        "additional_properties": False,
        "type_fields": _network_fields(),
        "event_schemas": {
            "*": {
                "required_fields": ["context", "network", "raw"],
                "fields": {},
            }
        },
    }
)
LOG_SCHEMAS["network"] = network_log_schema
_core.NETWORK_EVENTS = NETWORK_EVENTS
_core.NETWORK_ALLOWED = NETWORK_ALLOWED
_core._network_fields = _network_fields
_core.network_log_schema = network_log_schema
_core.LOG_SCHEMAS["network"] = network_log_schema


_original_infer_log_type = _core.infer_log_type


def infer_log_type(record: Dict[str, Any]) -> str:
    """Infer packet logs from the v4 shape; legacy HTTP events are not network."""
    if record.get("log_type") or record.get(_INTERNAL_LOG_TYPE):
        return _original_infer_log_type(record)
    if str(record.get("event", "")) == "packet":
        return "network"
    if (
        str(record.get("log_id", "")).startswith("net_")
        and all(name in record for name in ("context", "network", "raw"))
    ):
        return "network"
    return _original_infer_log_type(record)


_core.infer_log_type = infer_log_type


_original_emit = LogManager.emit


def _emit(
    self,
    record: Dict[str, Any],
    log_type: Optional[str] = None,
) -> Dict[str, Any]:
    source_record = dict(record)
    resolved_type = (
        normalize_log_type(log_type)
        if log_type
        else infer_log_type(source_record)
    )
    if resolved_type != "network":
        return _original_emit(self, source_record, log_type=resolved_type)

    event = str(source_record.pop("event", "") or "packet")
    source_record["timestamp"] = _packet_timestamp(
        source_record.get("timestamp", "")
    )
    source_record["log_id"] = str(
        source_record.get("log_id") or f"net_{uuid.uuid4().hex[:12]}"
    )
    normalized = _normalize_record_with_schema(
        source_record,
        network_log_schema,
        event,
    )
    self._append_memory(normalized, "network", event)
    self._write_file("network", normalized)
    return copy.deepcopy(normalized)


LogManager.emit = _emit


def _emit_network_event(
    self,
    context: Dict[str, Any],
    network: Dict[str, Any],
    raw: Dict[str, Any],
    timestamp: Any = "",
    log_id: str = "",
) -> Dict[str, Any]:
    """Persist one packet record using raw TShark layers as ``network``."""
    return self.emit(
        {
            "event": "packet",
            "timestamp": timestamp,
            "log_id": log_id,
            "context": context,
            "network": network,
            "raw": raw,
        },
        log_type="network",
    )


LogManager.emit_network_event = _emit_network_event


_original_increment_stats = LogManager._increment_stats


def _increment_stats(self, entry: Dict[str, Any]):
    _original_increment_stats(self, entry)
    if (entry.get("actor") or {}).get("agent_id"):
        return
    observer = (entry.get("context") or {}).get("observer_agent_id")
    if observer:
        self._stats["by_agent"][observer] = (
            self._stats["by_agent"].get(observer, 0) + 1
        )


LogManager._increment_stats = _increment_stats


_original_query = LogManager.query


def _query(
    self,
    agent_id=None,
    event=None,
    level=None,
    keyword=None,
    log_type=None,
    trace_id=None,
    task_id=None,
    limit=50,
):
    if not agent_id and not trace_id:
        return _original_query(
            self,
            agent_id=agent_id,
            event=event,
            level=level,
            keyword=keyword,
            log_type=log_type,
            trace_id=trace_id,
            task_id=task_id,
            limit=limit,
        )

    results = _original_query(
        self,
        agent_id=None,
        event=event,
        level=level,
        keyword=keyword,
        log_type=log_type,
        trace_id=None,
        task_id=task_id,
        limit=self._max,
    )
    if agent_id:
        results = [
            entry
            for entry in results
            if agent_id
            in {
                (entry.get("actor") or {}).get("agent_id"),
                (entry.get("target") or {}).get("agent_id"),
                (entry.get("context") or {}).get("observer_agent_id"),
            }
        ]
    if trace_id:
        results = [
            entry
            for entry in results
            if trace_id
            in {
                (entry.get("trace") or {}).get("trace_id"),
                ((entry.get("debug") or {}).get("context") or {}).get("trace_id"),
                (entry.get("context") or {}).get("trace_id"),
            }
        ]
    return results[-limit:]


LogManager.query = _query

# Keep the internal base module coherent for functions defined there.
_core.LogManager = LogManager
