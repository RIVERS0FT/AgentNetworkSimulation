from services import agent_server


def test_inbox_acknowledges_only_snapshot_messages():
    agent_server._clear_inbox()
    agent_server._append_inbox("a", "old")
    messages, message_ids = agent_server._snapshot_inbox()
    agent_server._append_inbox("b", "new")

    agent_server._ack_inbox(message_ids)
    remaining, _ = agent_server._snapshot_inbox()

    assert messages == [{"from": "a", "content": "old", "type": "direct", "channel_id": "", "trace_id": ""}]
    assert remaining == [{"from": "b", "content": "new", "type": "direct", "channel_id": "", "trace_id": ""}]
