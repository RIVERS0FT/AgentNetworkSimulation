"""SQLite-backed A2A task lifecycle store."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_STATES = {
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_REJECTED",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


class TaskManagerError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class TaskManager:
    """Persist inbound and outbound A2A tasks and their callback state."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._initialize()

    def _initialize(self) -> None:
        with self._db:
            self._db.execute("PRAGMA busy_timeout=5000")
            if self.db_path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    direction TEXT NOT NULL,
                    context_id TEXT NOT NULL,
                    simulation_id TEXT NOT NULL DEFAULT '',
                    source_agent_id TEXT NOT NULL DEFAULT '',
                    target_agent_id TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL,
                    goal TEXT NOT NULL DEFAULT '',
                    trace_id TEXT NOT NULL DEFAULT '',
                    parent_task_id TEXT NOT NULL DEFAULT '',
                    idempotency_key TEXT NOT NULL DEFAULT '',
                    task_json TEXT NOT NULL,
                    callback_json TEXT NOT NULL DEFAULT '{}',
                    callback_state TEXT NOT NULL DEFAULT '',
                    callback_sequence INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency
                    ON tasks(direction, source_agent_id, idempotency_key)
                    WHERE idempotency_key <> '';
                CREATE INDEX IF NOT EXISTS idx_tasks_pending
                    ON tasks(direction, target_agent_id, state, created_at);
                """
            )

    @staticmethod
    def _task_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return json.loads(row["task_json"]) if row else None

    def create_inbound(
        self,
        message: dict[str, Any],
        goal: str,
        source_agent_id: str,
        target_agent_id: str,
        callback_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = message.get("metadata") or {}
        idempotency_key = str(metadata.get("idempotencyKey") or "")
        with self._lock:
            if idempotency_key:
                row = self._db.execute(
                    "SELECT * FROM tasks WHERE direction='inbound' "
                    "AND source_agent_id=? AND idempotency_key=?",
                    (source_agent_id, idempotency_key),
                ).fetchone()
                existing = self._task_from_row(row)
                if existing:
                    return existing

            task_id = str(uuid.uuid4())
            context_id = str(message.get("contextId") or uuid.uuid4())
            now = _now_iso()
            task = {
                "id": task_id,
                "contextId": context_id,
                "status": {"state": "TASK_STATE_SUBMITTED", "timestamp": now},
                "history": [message],
                "metadata": {
                    **metadata,
                    "sourceAgentId": source_agent_id,
                    "targetAgentId": target_agent_id,
                },
            }
            with self._db:
                self._db.execute(
                    """INSERT INTO tasks (
                        task_id,direction,context_id,simulation_id,
                        source_agent_id,target_agent_id,state,goal,trace_id,
                        parent_task_id,idempotency_key,task_json,callback_json,
                        callback_state,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        task_id,
                        "inbound",
                        context_id,
                        str(metadata.get("simulationId") or ""),
                        source_agent_id,
                        target_agent_id,
                        "TASK_STATE_SUBMITTED",
                        goal,
                        str(metadata.get("traceId") or ""),
                        str(metadata.get("parentTaskId") or ""),
                        idempotency_key,
                        json.dumps(task, ensure_ascii=False),
                        json.dumps(callback_config or {}, ensure_ascii=False),
                        "pending" if callback_config else "disabled",
                        now,
                        now,
                    ),
                )
            return task

    def save_outbound(
        self,
        task: dict[str, Any],
        source_agent_id: str,
        target_agent_id: str,
        goal: str,
        idempotency_key: str = "",
        callback_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = task.get("metadata") or {}
        now = _now_iso()
        with self._lock, self._db:
            self._db.execute(
                """INSERT OR REPLACE INTO tasks (
                    task_id,direction,context_id,simulation_id,
                    source_agent_id,target_agent_id,state,goal,trace_id,
                    parent_task_id,idempotency_key,task_json,callback_json,
                    callback_state,callback_sequence,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    task["id"],
                    "outbound",
                    task.get("contextId", ""),
                    str(metadata.get("simulationId") or ""),
                    source_agent_id,
                    target_agent_id,
                    (task.get("status") or {}).get("state", "TASK_STATE_SUBMITTED"),
                    goal,
                    str(metadata.get("traceId") or ""),
                    str(metadata.get("parentTaskId") or ""),
                    idempotency_key,
                    json.dumps(task, ensure_ascii=False),
                    json.dumps(callback_config or {}, ensure_ascii=False),
                    "registered",
                    0,
                    now,
                    now,
                ),
            )
        return task

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        task = self._task_from_row(row)
        if task is None:
            raise TaskManagerError("TASK_NOT_FOUND", f"Task '{task_id}' was not found")
        return task

    def get_record(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        if row is None:
            raise TaskManagerError("TASK_NOT_FOUND", f"Task '{task_id}' was not found")
        result = dict(row)
        result["task"] = json.loads(result.pop("task_json"))
        result["callback"] = json.loads(result.pop("callback_json"))
        return result

    def list_tasks(
        self,
        context_id: str = "",
        status: str = "",
        simulation_id: str = "",
        page_size: int = 50,
        include_artifacts: bool = False,
    ) -> dict[str, Any]:
        clauses, values = [], []
        if context_id:
            clauses.append("context_id=?")
            values.append(context_id)
        if status:
            clauses.append("state=?")
            values.append(status)
        if simulation_id:
            clauses.append("simulation_id=?")
            values.append(simulation_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        page_size = max(1, min(int(page_size), 100))
        with self._lock:
            total = self._db.execute(
                f"SELECT COUNT(*) FROM tasks {where}", values
            ).fetchone()[0]
            rows = self._db.execute(
                f"SELECT task_json FROM tasks {where} ORDER BY created_at LIMIT ?",
                [*values, page_size],
            ).fetchall()
        tasks = []
        for row in rows:
            task = json.loads(row["task_json"])
            if not include_artifacts:
                task.pop("artifacts", None)
            tasks.append(task)
        return {
            "tasks": tasks,
            "nextPageToken": "",
            "pageSize": page_size,
            "totalSize": total,
        }

    def transition(
        self,
        task_id: str,
        state: str,
        artifacts: list[dict[str, Any]] | None = None,
        status_message: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            record = self.get_record(task_id)
            task = record["task"]
            current = (task.get("status") or {}).get("state", "")
            if current in TERMINAL_STATES and current != state:
                raise TaskManagerError(
                    "INVALID_TASK_TRANSITION",
                    f"Task '{task_id}' is already terminal ({current})",
                )
            status = {"state": state, "timestamp": _now_iso()}
            if status_message:
                status["message"] = {
                    "messageId": str(uuid.uuid4()),
                    "contextId": task.get("contextId", ""),
                    "taskId": task_id,
                    "role": "ROLE_AGENT",
                    "parts": [{"text": status_message, "mediaType": "text/plain"}],
                }
            task["status"] = status
            if artifacts is not None:
                task["artifacts"] = artifacts
            with self._db:
                self._db.execute(
                    "UPDATE tasks SET state=?,task_json=?,updated_at=? WHERE task_id=?",
                    (state, json.dumps(task, ensure_ascii=False), _now_iso(), task_id),
                )
            return task

    def claim_next(self, target_agent_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT task_id FROM tasks WHERE direction='inbound' "
                "AND target_agent_id=? AND state='TASK_STATE_SUBMITTED' "
                "ORDER BY created_at LIMIT 1",
                (target_agent_id,),
            ).fetchone()
            if not row:
                return None
            task = self.transition(row["task_id"], "TASK_STATE_WORKING")
            return self.get_record(task["id"])

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        state = (task.get("status") or {}).get("state", "")
        if state in TERMINAL_STATES:
            raise TaskManagerError("TASK_NOT_CANCELABLE", f"Task '{task_id}' is terminal")
        return self.transition(task_id, "TASK_STATE_CANCELED")

    def apply_callback(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = payload.get("statusUpdate") or payload.get("artifactUpdate") or {}
        task_id = str(event.get("taskId") or "")
        if not task_id:
            raise TaskManagerError("INVALID_CALLBACK", "callback taskId is required")
        task = self.get_task(task_id)
        if payload.get("statusUpdate"):
            task["status"] = event.get("status") or task.get("status")
        else:
            artifact = event.get("artifact") or {}
            artifacts = list(task.get("artifacts") or [])
            artifacts.append(artifact)
            task["artifacts"] = artifacts
        metadata = event.get("metadata") or {}
        sequence = int(metadata.get("sequence") or 0)
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT callback_sequence FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if row and sequence and sequence <= row["callback_sequence"]:
                return self.get_task(task_id)
            state = (task.get("status") or {}).get("state", "TASK_STATE_SUBMITTED")
            self._db.execute(
                "UPDATE tasks SET state=?,task_json=?,callback_state='received',"
                "callback_sequence=?,updated_at=? WHERE task_id=?",
                (state, json.dumps(task, ensure_ascii=False), sequence, _now_iso(), task_id),
            )
        return task

    def callback_config(self, task_id: str) -> dict[str, Any]:
        return self.get_record(task_id)["callback"]

    def set_callback_config(
        self, task_id: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        self.get_task(task_id)
        normalized = dict(config or {})
        normalized.setdefault("id", str(uuid.uuid4()))
        normalized["taskId"] = task_id
        with self._lock, self._db:
            self._db.execute(
                "UPDATE tasks SET callback_json=?,callback_state='pending',updated_at=? "
                "WHERE task_id=?",
                (json.dumps(normalized, ensure_ascii=False), _now_iso(), task_id),
            )
        return normalized

    def delete_callback_config(self, task_id: str, config_id: str) -> None:
        config = self.callback_config(task_id)
        if config and config.get("id") != config_id:
            raise TaskManagerError(
                "PUSH_NOTIFICATION_CONFIG_NOT_FOUND",
                f"Push notification config '{config_id}' was not found",
            )
        with self._lock, self._db:
            self._db.execute(
                "UPDATE tasks SET callback_json='{}',callback_state='disabled',"
                "updated_at=? WHERE task_id=?",
                (_now_iso(), task_id),
            )

    def mark_callback(self, task_id: str, delivered: bool, sequence: int) -> None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE tasks SET callback_state=?,callback_sequence=?,updated_at=? "
                "WHERE task_id=?",
                ("delivered" if delivered else "pending", sequence, _now_iso(), task_id),
            )

    def count_pending(self, target_agent_id: str) -> int:
        with self._lock:
            return self._db.execute(
                "SELECT COUNT(*) FROM tasks WHERE direction='inbound' "
                "AND target_agent_id=? AND state='TASK_STATE_SUBMITTED'",
                (target_agent_id,),
            ).fetchone()[0]

    def clear(self) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM tasks")
