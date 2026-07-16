"""A2A task push-notification delivery."""

from __future__ import annotations

import uuid
from typing import Any

import requests

from .task_manager import TaskManager


class CallbackDispatcher:
    def __init__(
        self,
        tasks: TaskManager,
        session: requests.Session | None = None,
        timeout_seconds: float = 5,
    ):
        self.tasks = tasks
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def dispatch_status(self, task: dict[str, Any]) -> bool:
        config = self.tasks.callback_config(task["id"])
        if not config.get("url"):
            return True
        record = self.tasks.get_record(task["id"])
        sequence = int(record.get("callback_sequence") or 0) + 1
        payload = {
            "statusUpdate": {
                "taskId": task["id"],
                "contextId": task.get("contextId", ""),
                "status": task.get("status") or {},
                "metadata": {
                    "eventId": str(uuid.uuid4()),
                    "sequence": sequence,
                    **(task.get("metadata") or {}),
                },
            }
        }
        return self._post(task["id"], config, payload, sequence)

    def dispatch_artifacts(self, task: dict[str, Any]) -> bool:
        config = self.tasks.callback_config(task["id"])
        if not config.get("url"):
            return True
        ok = True
        for artifact in task.get("artifacts") or []:
            record = self.tasks.get_record(task["id"])
            sequence = int(record.get("callback_sequence") or 0) + 1
            payload = {
                "artifactUpdate": {
                    "taskId": task["id"],
                    "contextId": task.get("contextId", ""),
                    "artifact": artifact,
                    "lastChunk": True,
                    "metadata": {
                        "eventId": str(uuid.uuid4()),
                        "sequence": sequence,
                        **(task.get("metadata") or {}),
                    },
                }
            }
            ok = self._post(task["id"], config, payload, sequence) and ok
        return ok

    def _post(
        self,
        task_id: str,
        config: dict[str, Any],
        payload: dict[str, Any],
        sequence: int,
    ) -> bool:
        headers = {"A2A-Version": "1.0", "Content-Type": "application/a2a+json"}
        token = config.get("token")
        if token:
            headers["X-A2A-Notification-Token"] = str(token)
        try:
            response = self.session.post(
                config["url"],
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            self.tasks.mark_callback(task_id, True, sequence)
            return True
        except Exception:
            self.tasks.mark_callback(task_id, False, sequence)
            return False
