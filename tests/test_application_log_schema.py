import json
import os

import pytest

from agent_network.log_manager import (
    LogManager,
    application_log_schema,
    network_log_schema,
    system_log_schema,
)


REMOVED_FIELDS = {
    "seq",
    "session_id",
    "tick",
    "layer",
    "message",
    "category",
    "component",
}
SYSTEM_ONLY_FIELDS = {"level", "source", "debug"}
EVENT_IDENTITY_FIELDS = {
    "event",
    "event_id",
    "parent_event_id",
    "actor",
    "trace",
}
REMOVED_BEHAVIOR_EVENTS = {
    "decide",
    "agent_decide",
    "act",
    "agent_action",
}


@pytest.fixture
def manager(tmp_path):
    instance = LogManager(log_dir=str(tmp_path))
    instance.reset()
    instance._log_dir = str(tmp_path)
    os.makedirs(instance._log_dir, exist_ok=True)
    yield instance
    instance.reset()


@pytest.mark.not_llm
def test_each_schema_owns_timestamp_field():
    schemas = (
        application_log_schema,
        network_log_schema,
        system_log_schema,
    )
    for schema in schemas:
        assert "common_fields" not in schema
        assert schema["type_fields"]["timestamp"] == {
            "type": "string",
            "required": True,
        }

    assert application_log_schema["type_fields"] is not network_log_schema["type_fields"]
    assert application_log_schema["type_fields"] is not system_log_schema["type_fields"]
    assert network_log_schema["type_fields"] is not system_log_schema["type_fields"]


@pytest.mark.not_llm
def test_application_schema_uses_reasoning_and_acting_only():
    schemas = application_log_schema["event_schemas"]

    assert "reasoning" in schemas
    assert "acting" in schemas
    assert not (REMOVED_BEHAVIOR_EVENTS & set(schemas))
    assert schemas["reasoning"]["required_fields"] == ["action", "decision"]
    assert schemas["acting"]["required_fields"] == ["action"]


@pytest.mark.not_llm
def test_application_schema_field_boundary(manager):
    record = manager.emit_application_event(
        event="test_event",
        actor={"agent_id": "test_agent"},
    )

    assert record["event"] == "test_event"
    assert record["actor"]["agent_id"] == "test_agent"
    assert EVENT_IDENTITY_FIELDS <= set(record)
    assert not (REMOVED_FIELDS & set(record))
    assert not (SYSTEM_ONLY_FIELDS & set(record))
    assert "trace_id" in record["trace"]
    assert "trace_id" not in record
    assert "timestamp" in record


@pytest.mark.not_llm
def test_network_schema_field_boundary(manager):
    record = manager.emit_network_event(
        event="docker_http_outbound",
        actor={"agent_id": "agent_a"},
        network={"direction": "outbound"},
    )

    assert EVENT_IDENTITY_FIELDS <= set(record)
    assert record["network"]["direction"] == "outbound"
    assert not (REMOVED_FIELDS & set(record))
    assert not (SYSTEM_ONLY_FIELDS & set(record))


@pytest.mark.not_llm
def test_system_schema_and_source_component_merge(manager):
    record = manager.emit_system_event(
        event="debug_snapshot",
        message="snapshot ready",
        category="debug",
        source="backend",
        component="srv",
        debug={"request_id": "r1"},
    )

    assert record["source"] == "backend.srv"
    assert record["level"] == "INFO"
    assert record["debug"]["event"] == "debug_snapshot"
    assert record["debug"]["kind"] == "debug"
    assert record["payload"]["message"] == "snapshot ready"
    assert not (EVENT_IDENTITY_FIELDS & set(record))
    assert not (REMOVED_FIELDS & set(record))


@pytest.mark.not_llm
def test_persisted_jsonl_has_no_removed_fields(manager):
    session_id = manager.start_session("schema_test")
    manager.emit_application_event(
        event="acting",
        actor={"agent_id": "a1"},
        action={"name": "move"},
    )
    manager.emit_network_event(
        event="docker_http_outbound",
        network={"direction": "outbound"},
    )
    manager._close_file_handles()

    for filename in ("application.jsonl", "network.jsonl", "system.jsonl"):
        path = os.path.join(manager._log_dir, session_id, filename)
        with open(path, "r", encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                assert not (REMOVED_FIELDS & set(record))
                assert "timestamp" in record


@pytest.mark.not_llm
def test_agent_message_strips_network_and_system_fields(manager):
    record = manager.agent_message(
        from_id="a1",
        to="a2",
        content="hello",
        latency_ms=12.5,
        src_ip="192.168.1.1",
        tcp_flags="SYN",
        payload_len=100,
    )

    assert record["action"]["duration_ms"] == 12.5
    assert record["content"]["size_bytes"] == 100
    assert "network" not in record
    assert "src_ip" not in record
    assert "tcp_flags" not in record
    assert not (SYSTEM_ONLY_FIELDS & set(record))


@pytest.mark.not_llm
def test_reasoning_and_acting_helpers(manager):
    action = manager.acting("a1", "move", {"status": "ok"}, extra="data")
    reasoning = manager.reasoning("a1", "prompt", {"choice": "A"})

    assert action["event"] == "acting"
    assert action["content"]["kw"] == {"extra": "data"}
    assert reasoning["event"] == "reasoning"
    assert reasoning["decision"]["raw_model_output_ref"] == "prompt"
    assert not hasattr(manager, "agent_action")
    assert not hasattr(manager, "agent_decide")


@pytest.mark.not_llm
@pytest.mark.parametrize("event", sorted(REMOVED_BEHAVIOR_EVENTS))
def test_removed_behavior_events_are_rejected(manager, event):
    with pytest.raises(ValueError, match="has been removed"):
        manager.emit_application_event(
            event=event,
            actor={"agent_id": "a1"},
            action={"name": event},
            decision={"summary": "legacy"},
        )
