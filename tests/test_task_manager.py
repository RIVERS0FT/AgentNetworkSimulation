from agent_network.task_management import CallbackDispatcher, TaskManager


def _message(idempotency_key="task-key"):
    return {
        "messageId": "message-1",
        "contextId": "context-1",
        "role": "ROLE_USER",
        "parts": [{"text": "do work", "mediaType": "text/plain"}],
        "metadata": {
            "simulationId": "sim-1",
            "traceId": "trace-1",
            "idempotencyKey": idempotency_key,
        },
    }


def test_task_manager_persists_lifecycle_and_idempotency(tmp_path):
    path = tmp_path / "tasks.db"
    tasks = TaskManager(str(path))
    first = tasks.create_inbound(_message(), "do work", "agent-a", "agent-b")
    second = tasks.create_inbound(_message(), "do work", "agent-a", "agent-b")

    assert first["id"] == second["id"]
    claimed = tasks.claim_next("agent-b")
    assert claimed["task"]["status"]["state"] == "TASK_STATE_WORKING"
    completed = tasks.transition(
        first["id"],
        "TASK_STATE_COMPLETED",
        artifacts=[{"artifactId": "artifact-1", "parts": [{"text": "done"}]}],
    )
    assert completed["artifacts"][0]["artifactId"] == "artifact-1"

    reopened = TaskManager(str(path))
    assert reopened.get_task(first["id"])["status"]["state"] == "TASK_STATE_COMPLETED"


def test_callback_dispatcher_posts_authenticated_ordered_events():
    class Response:
        def raise_for_status(self):
            return None

    class Session:
        def __init__(self):
            self.calls = []

        def post(self, url, json, headers, timeout):
            self.calls.append((url, json, headers, timeout))
            return Response()

    tasks = TaskManager()
    task = tasks.create_inbound(
        _message("callback-key"),
        "do work",
        "agent-a",
        "agent-b",
        {"id": "callback-1", "url": "http://agent-a/events", "token": "secret"},
    )
    task = tasks.transition(task["id"], "TASK_STATE_WORKING")
    session = Session()

    assert CallbackDispatcher(tasks, session=session).dispatch_status(task)
    _, payload, headers, _ = session.calls[0]
    assert headers["A2A-Version"] == "1.0"
    assert headers["X-A2A-Notification-Token"] == "secret"
    assert payload["statusUpdate"]["metadata"]["sequence"] == 1
    assert tasks.get_record(task["id"])["callback_state"] == "delivered"


def test_callback_sequence_deduplicates_replayed_artifacts():
    tasks = TaskManager()
    task = {
        "id": "outbound-1",
        "contextId": "context-1",
        "status": {"state": "TASK_STATE_SUBMITTED"},
        "metadata": {"simulationId": "sim-1"},
    }
    tasks.save_outbound(task, "srv", "agent-b", "do work")
    payload = {
        "artifactUpdate": {
            "taskId": "outbound-1",
            "artifact": {"artifactId": "artifact-1", "parts": [{"text": "done"}]},
            "metadata": {"sequence": 2},
        }
    }

    tasks.apply_callback(payload)
    tasks.apply_callback(payload)

    assert len(tasks.get_task("outbound-1")["artifacts"]) == 1
