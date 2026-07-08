import os

import pytest

from agent_network.log_manager import LogManager


@pytest.fixture
def manager(tmp_path):
    instance = LogManager(log_dir=str(tmp_path))
    instance.reset()
    instance._log_dir = str(tmp_path)
    os.makedirs(instance._log_dir, exist_ok=True)
    yield instance
    instance.reset()


@pytest.mark.not_llm
def test_layered_recording_without_global_log(manager):
    session_id = manager.start_session("test_scene")
    manager.emit_application_event(
        event="act",
        actor={"agent_id": "a1"},
        action={"name": "move"},
    )
    manager.emit_network_event(
        event="docker_http_outbound",
        actor={"agent_id": "a1"},
        network={"direction": "outbound"},
    )
    manager.emit_system_event(event="debug_snapshot", payload={"ready": True})
    manager._close_file_handles()

    session_dir = os.path.join(manager._log_dir, session_id)
    assert os.path.isfile(os.path.join(session_dir, "application.jsonl"))
    assert os.path.isfile(os.path.join(session_dir, "network.jsonl"))
    assert os.path.isfile(os.path.join(session_dir, "system.jsonl"))
    assert not os.path.exists(os.path.join(session_dir, "global.jsonl"))


@pytest.mark.not_llm
def test_hide_show_download_and_delete(manager):
    session_id = manager.start_session("test_scene")
    manager.emit_network_event(
        event="docker_http_outbound",
        network={"direction": "outbound"},
    )

    download_path = manager.get_download_path(session_id, "network")
    assert os.path.isfile(download_path)

    manager.hide_log(session_id, "network")
    visible_files = manager.list_log_files()
    assert all(
        item["type"] != "network"
        for session in visible_files
        for item in session["files"]
    )

    hidden_files = manager.list_log_files(include_hidden=True)
    network_file = next(
        item
        for session in hidden_files
        for item in session["files"]
        if item["type"] == "network"
    )
    assert network_file["visible"] is False

    manager.show_log(session_id, "network")
    assert any(
        item["type"] == "network"
        for session in manager.list_log_files()
        for item in session["files"]
    )

    result = manager.delete_log(session_id, "network")
    assert result["deleted"] is True
    assert not os.path.exists(download_path)
