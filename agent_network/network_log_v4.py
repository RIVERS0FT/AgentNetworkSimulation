"""Install the packet-oriented network.jsonl v4 schema.

The project is still in early development, so this module replaces the legacy
HTTP-oriented network log contract without compatibility shims.  It is loaded
from ``agent_network.__init__`` before callers import ``agent_network.log_manager``.
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


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


def apply() -> None:
    """Replace the legacy network schema and LogManager network entry points."""
    from . import log_manager as module

    if getattr(module, "_NETWORK_LOG_V4_APPLIED", False):
        return

    context_fields = {
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
    context_spec = module._object(
        properties=context_fields,
        required_properties=list(context_fields),
    )

    raw_fields = {
        "format": {"type": "string"},
        "encoding": {"type": "string"},
        "data": {"type": "string"},
        "byte_length": {"type": "integer"},
        "packet_count": {"type": "integer"},
        "sha256": {"type": "string"},
    }
    raw_spec = module._object(
        properties=raw_fields,
        required_properties=list(raw_fields),
    )

    module.NETWORK_EVENTS = frozenset({"packet"})
    module.NETWORK_ALLOWED = ("context", "network", "raw")
    module.network_log_schema.clear()
    module.network_log_schema.update(
        {
            "name": "network.jsonl",
            "format": "jsonl",
            "log_type": "network",
            "schema_version": "network.v4",
            "additional_properties": False,
            "type_fields": {
                "timestamp": {"type": "string", "required": True},
                "log_id": {"type": "string", "required": True},
                "context": context_spec,
                # TShark packet["_source"]["layers"] is stored verbatim here.
                "network": module._object(),
                "raw": raw_spec,
            },
            "event_schemas": {
                "*": {
                    "required_fields": ["context", "network", "raw"],
                    "fields": {},
                }
            },
        }
    )
    module.LOG_SCHEMAS["network"] = module.network_log_schema

    original_infer_log_type = module.infer_log_type

    def infer_log_type(record: Dict[str, Any]) -> str:
        if record.get("log_type") or record.get(module._INTERNAL_LOG_TYPE):
            return original_infer_log_type(record)
        if (
            str(record.get("log_id", "")).startswith("net_")
            and all(name in record for name in ("context", "network", "raw"))
        ):
            return "network"
        return original_infer_log_type(record)

    module.infer_log_type = infer_log_type

    original_emit = module.LogManager.emit

    def emit(
        self,
        record: Dict[str, Any],
        log_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        source_record = dict(record)
        resolved_type = (
            module.normalize_log_type(log_type)
            if log_type
            else module.infer_log_type(source_record)
        )
        if resolved_type != "network":
            return original_emit(self, source_record, log_type=resolved_type)

        event = str(source_record.pop("event", "") or "packet")
        source_record["timestamp"] = _packet_timestamp(
            source_record.get("timestamp", "")
        )
        source_record["log_id"] = str(
            source_record.get("log_id") or f"net_{uuid.uuid4().hex[:12]}"
        )
        normalized = module._normalize_record_with_schema(
            source_record,
            module.network_log_schema,
            event,
        )
        self._append_memory(normalized, "network", event)
        self._write_file("network", normalized)
        return copy.deepcopy(normalized)

    module.LogManager.emit = emit

    def emit_network_event(
        self,
        context: Dict[str, Any],
        network: Dict[str, Any],
        raw: Dict[str, Any],
        timestamp: Any = "",
        log_id: str = "",
    ) -> Dict[str, Any]:
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

    module.LogManager.emit_network_event = emit_network_event

    original_increment_stats = module.LogManager._increment_stats

    def _increment_stats(self, entry: Dict[str, Any]):
        original_increment_stats(self, entry)
        if (entry.get("actor") or {}).get("agent_id"):
            return
        observer = (entry.get("context") or {}).get("observer_agent_id")
        if observer:
            self._stats["by_agent"][observer] = (
                self._stats["by_agent"].get(observer, 0) + 1
            )

    module.LogManager._increment_stats = _increment_stats

    original_query = module.LogManager.query

    def query(
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
            return original_query(
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

        results = original_query(
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
                    ((entry.get("debug") or {}).get("context") or {}).get(
                        "trace_id"
                    ),
                    (entry.get("context") or {}).get("trace_id"),
                }
            ]
        return results[-limit:]

    module.LogManager.query = query
    module._NETWORK_LOG_V4_APPLIED = True
