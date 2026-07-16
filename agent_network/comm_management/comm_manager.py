"""Unified point-to-point Agent communication using the A2A 1.0 REST binding.

The manager is the only Agent communication entry point.  It owns discovery,
topology authorization, A2A request construction, sequential multi-target
delivery, inbound delivery, and the small task store used for delivery receipts.
There is intentionally no broadcast operation.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import requests

from agent_network.task_management import TaskManager, TaskManagerError


A2A_PROTOCOL_VERSION = "1.0"
A2A_MEDIA_TYPE = "application/a2a+json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


class CommunicationError(RuntimeError):
    """Protocol or authorization error raised while accepting a message."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass
class SendResult:
    target: str
    status: str
    message_id: str
    task_id: str = ""
    context_id: str = ""
    error: str = ""
    response: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchSendResult:
    status: str
    results: list[SendResult]

    @property
    def ok(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "results": [result.to_dict() for result in self.results],
        }


class CommManager:
    """Manage authorized, point-to-point A2A communication for one Agent."""

    def __init__(
        self,
        agent_id: str = "",
        agent_name: str = "",
        agent_role: str = "generic",
        agent_directory: dict[str, str] | None = None,
        comm_matrix: dict[str, Iterable[str]] | None = None,
        inbox_handler: Callable[..., None] | None = None,
        session: requests.Session | None = None,
        timeout_seconds: float = 10,
        task_manager: TaskManager | None = None,
        trusted_task_sources: Iterable[str] | None = None,
    ):
        self.agent_id = str(agent_id).lower()
        self.agent_name = agent_name or self.agent_id
        self.agent_role = agent_role or "generic"
        self.timeout_seconds = timeout_seconds
        self._session = session or requests.Session()
        self._inbox_handler = inbox_handler
        self._directory: dict[str, str] = {}
        self._comm_matrix: dict[str, set[str]] = {}
        self._matrix_configured = comm_matrix is not None
        self._card_cache: dict[str, dict[str, Any]] = {}
        self._tasks: dict[str, dict[str, Any]] = {}
        self._task_lock = threading.Lock()
        self.task_manager = task_manager or TaskManager()
        self.trusted_task_sources = {
            str(source).lower() for source in (trusted_task_sources or {"srv"})
        }
        self.update_directory(agent_directory, comm_matrix)

    def set_identity(self, agent_id: str, agent_name: str = "", agent_role: str = ""):
        self.agent_id = str(agent_id).lower()
        self.agent_name = agent_name or self.agent_name or self.agent_id
        self.agent_role = agent_role or self.agent_role

    def set_inbox_handler(self, handler: Callable[..., None] | None) -> None:
        self._inbox_handler = handler

    def update_directory(
        self,
        agent_directory: dict[str, str] | None = None,
        comm_matrix: dict[str, Iterable[str]] | None = None,
    ) -> None:
        if agent_directory is not None:
            self._directory = {
                str(agent_id).lower(): str(url).rstrip("/")
                for agent_id, url in agent_directory.items()
                if url
            }
            self._card_cache.clear()
        if comm_matrix is not None:
            self._comm_matrix = {
                str(source).lower(): {
                    str(target).lower() for target in (targets or [])
                }
                for source, targets in comm_matrix.items()
            }
            self._matrix_configured = True

    def register_agent(self, agent_id: str, card_url: str) -> None:
        normalized = str(agent_id).lower()
        self._directory[normalized] = str(card_url).rstrip("/")
        self._card_cache.pop(normalized, None)

    def _allowed(self, source: str, target: str) -> bool:
        if not self._matrix_configured:
            return True
        return target in self._comm_matrix.get(source, set())

    @staticmethod
    def _card_url(directory_url: str) -> str:
        if directory_url.endswith("/.well-known/agent-card.json"):
            return directory_url
        return f"{directory_url.rstrip('/')}/.well-known/agent-card.json"

    def _resolve_interface(self, target: str) -> str:
        directory_url = self._directory.get(target)
        if not directory_url:
            raise CommunicationError(
                "AGENT_NOT_FOUND", f"Agent '{target}' is not registered", 404
            )

        card = self._card_cache.get(target)
        if card is None:
            response = self._session.get(
                self._card_url(directory_url), timeout=self.timeout_seconds
            )
            response.raise_for_status()
            card = response.json()
            self._card_cache[target] = card

        for interface in card.get("supportedInterfaces") or []:
            if (
                interface.get("protocolVersion") == A2A_PROTOCOL_VERSION
                and interface.get("protocolBinding") == "HTTP+JSON"
                and interface.get("url")
            ):
                return str(interface["url"]).rstrip("/")
        raise CommunicationError(
            "A2A_INTERFACE_NOT_FOUND",
            f"Agent '{target}' does not advertise an A2A 1.0 HTTP+JSON interface",
            422,
        )

    def send_message(
        self,
        from_id: str,
        from_name: str,
        target: str,
        content: str,
        channel_id: str = "",
        trace_id: str = "",
    ) -> SendResult:
        source_id = str(from_id).lower()
        target_id = str(target).lower()
        message_id = str(uuid.uuid4())
        context_id = channel_id or str(uuid.uuid4())
        result = SendResult(
            target=target_id,
            status="failed",
            message_id=message_id,
            context_id=context_id,
        )

        if not source_id or not target_id:
            result.error = "source and target Agent IDs are required"
            return result
        if source_id == target_id:
            result.error = "self-send is not allowed"
            return result
        if not self._allowed(source_id, target_id):
            result.error = f"communication from '{source_id}' to '{target_id}' is denied"
            return result

        payload = {
            "message": {
                "messageId": message_id,
                "contextId": context_id,
                "role": "ROLE_USER",
                "parts": [{"text": str(content), "mediaType": "text/plain"}],
                "metadata": {
                    "fromAgentId": source_id,
                    "fromAgentName": from_name,
                    "targetAgentId": target_id,
                    "traceId": trace_id,
                },
            },
            "configuration": {
                "acceptedOutputModes": ["text/plain"],
                "returnImmediately": True,
            },
        }
        headers = {
            "A2A-Version": A2A_PROTOCOL_VERSION,
            "Content-Type": A2A_MEDIA_TYPE,
            "Accept": A2A_MEDIA_TYPE,
        }
        try:
            interface_url = self._resolve_interface(target_id)
            response = self._session.post(
                f"{interface_url}/message:send",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            task = body.get("task") or {}
            response_message = body.get("message") or {}
            if not task and not response_message:
                raise CommunicationError(
                    "INVALID_A2A_RESPONSE",
                    "A2A response must contain task or message",
                    502,
                )
            result.status = "success"
            result.task_id = str(task.get("id", ""))
            result.context_id = str(
                task.get("contextId")
                or response_message.get("contextId")
                or context_id
            )
            result.response = body
        except Exception as exc:
            result.error = str(exc)
        return result

    def send_to_many(
        self,
        from_id: str,
        from_name: str,
        targets: Iterable[str],
        content: str,
        channel_id: str = "",
        trace_id: str = "",
    ) -> BatchSendResult:
        """Send sequentially, preserving first-seen target order."""
        if isinstance(targets, (str, bytes)):
            raise TypeError("targets must be an iterable of Agent IDs, not a string")
        ordered_targets = list(
            dict.fromkeys(str(target).lower() for target in targets if target)
        )
        results = [
            self.send_message(
                from_id,
                from_name,
                target,
                content,
                channel_id,
                trace_id,
            )
            for target in ordered_targets
        ]
        succeeded = sum(result.ok for result in results)
        if succeeded == len(results):
            status = "success"
        elif succeeded:
            status = "partial"
        else:
            status = "failed"
        return BatchSendResult(status=status, results=results)

    def delegate_task(
        self,
        from_id: str,
        from_name: str,
        target: str,
        goal: str,
        input_data: dict[str, Any] | None = None,
        context_id: str = "",
        trace_id: str = "",
        simulation_id: str = "",
        parent_task_id: str = "",
        idempotency_key: str = "",
        callback_url: str = "",
        callback_token: str = "",
    ) -> SendResult:
        source_id = str(from_id).lower()
        target_id = str(target).lower()
        message_id = str(uuid.uuid4())
        context_id = context_id or str(uuid.uuid4())
        result = SendResult(
            target=target_id,
            status="failed",
            message_id=message_id,
            context_id=context_id,
        )
        if not source_id or not target_id or not goal:
            result.error = "source, target and task goal are required"
            return result
        if source_id == target_id:
            result.error = "self-delegation is not allowed"
            return result
        if source_id not in self.trusted_task_sources and not self._allowed(
            source_id, target_id
        ):
            result.error = f"communication from '{source_id}' to '{target_id}' is denied"
            return result
        if not callback_url:
            source_url = self._directory.get(source_id, "")
            if source_url:
                callback_url = f"{source_url.rstrip('/')}/a2a/v1/task-events"
        callback_config = {
            "id": str(uuid.uuid4()),
            "url": callback_url,
            "token": callback_token or uuid.uuid4().hex,
        }
        payload = {
            "message": {
                "messageId": message_id,
                "contextId": context_id,
                "role": "ROLE_USER",
                "parts": [
                    {"text": str(goal), "mediaType": "text/plain"},
                    {
                        "data": {"input": input_data or {}},
                        "mediaType": "application/json",
                    },
                ],
                "metadata": {
                    "operation": "agent.task.assign",
                    "fromAgentId": source_id,
                    "fromAgentName": from_name,
                    "targetAgentId": target_id,
                    "simulationId": simulation_id,
                    "parentTaskId": parent_task_id,
                    "traceId": trace_id,
                    "idempotencyKey": idempotency_key,
                },
            },
            "configuration": {
                "acceptedOutputModes": ["text/plain", "application/json"],
                "returnImmediately": True,
                "taskPushNotificationConfig": callback_config,
            },
        }
        headers = {
            "A2A-Version": A2A_PROTOCOL_VERSION,
            "Content-Type": A2A_MEDIA_TYPE,
            "Accept": A2A_MEDIA_TYPE,
        }
        try:
            interface_url = self._resolve_interface(target_id)
            response = self._session.post(
                f"{interface_url}/message:send",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            task = body.get("task") or {}
            if not task.get("id"):
                raise CommunicationError(
                    "INVALID_A2A_RESPONSE", "delegated task response is required", 502
                )
            task["metadata"] = {
                **payload["message"]["metadata"],
                **(task.get("metadata") or {}),
            }
            self.task_manager.save_outbound(
                task,
                source_agent_id=source_id,
                target_agent_id=target_id,
                goal=goal,
                idempotency_key=idempotency_key,
                callback_config=callback_config,
            )
            result.status = "success"
            result.task_id = task["id"]
            result.context_id = task.get("contextId") or context_id
            result.response = body
        except Exception as exc:
            result.error = str(exc)
        return result

    def delegate_to_many(
        self,
        from_id: str,
        from_name: str,
        targets: Iterable[str],
        goal: str,
        **kwargs,
    ) -> BatchSendResult:
        if isinstance(targets, (str, bytes)):
            raise TypeError("targets must be an iterable of Agent IDs, not a string")
        ordered = list(dict.fromkeys(str(target).lower() for target in targets if target))
        results = [
            self.delegate_task(from_id, from_name, target, goal, **kwargs)
            for target in ordered
        ]
        succeeded = sum(result.ok for result in results)
        status = "success" if succeeded == len(results) else "partial" if succeeded else "failed"
        return BatchSendResult(status=status, results=results)

    @staticmethod
    def _message_text(message: dict[str, Any]) -> str:
        texts = [
            str(part.get("text"))
            for part in message.get("parts") or []
            if isinstance(part, dict) and part.get("text") is not None
        ]
        if not texts:
            raise CommunicationError(
                "CONTENT_TYPE_NOT_SUPPORTED",
                "At least one text Part is required",
                415,
            )
        return "\n".join(texts)

    def receive_message(self, request: dict[str, Any]) -> dict[str, Any]:
        message = request.get("message") if isinstance(request, dict) else None
        if not isinstance(message, dict):
            raise CommunicationError(
                "INVALID_REQUEST", "SendMessageRequest.message is required"
            )
        message_id = str(message.get("messageId") or "")
        if not message_id:
            raise CommunicationError(
                "INVALID_REQUEST", "Message.messageId is required"
            )
        if message.get("role") not in {"ROLE_USER", "user"}:
            raise CommunicationError(
                "INVALID_REQUEST", "Client message role must be ROLE_USER"
            )

        metadata = message.get("metadata") or {}
        source_id = str(metadata.get("fromAgentId") or "").lower()
        target_id = str(metadata.get("targetAgentId") or self.agent_id).lower()
        if not source_id:
            raise CommunicationError(
                "INVALID_REQUEST", "metadata.fromAgentId is required"
            )
        if self.agent_id and target_id != self.agent_id:
            raise CommunicationError(
                "TARGET_MISMATCH",
                f"Message targets '{target_id}', not '{self.agent_id}'",
                409,
            )
        operation = str(metadata.get("operation") or "message")
        task_assignment = operation == "agent.task.assign"
        if (
            not (task_assignment and source_id in self.trusted_task_sources)
            and not self._allowed(source_id, target_id)
        ):
            raise CommunicationError(
                "COMMUNICATION_DENIED",
                f"communication from '{source_id}' to '{target_id}' is denied",
                403,
            )

        content = self._message_text(message)
        context_id = str(message.get("contextId") or uuid.uuid4())
        trace_id = str(metadata.get("traceId") or "")
        if task_assignment:
            callback_config = (
                (request.get("configuration") or {}).get(
                    "taskPushNotificationConfig"
                )
                or {}
            )
            if not callback_config.get("url") or not callback_config.get("token"):
                raise CommunicationError(
                    "INVALID_REQUEST",
                    "delegated tasks require a callback url and token",
                )
            task = self.task_manager.create_inbound(
                message=message,
                goal=content,
                source_agent_id=source_id,
                target_agent_id=target_id,
                callback_config=callback_config,
            )
            return {"task": task}
        if self._inbox_handler:
            self._inbox_handler(
                source_id,
                content,
                "a2a",
                context_id,
                trace_id,
            )

        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "contextId": context_id,
            "status": {
                "state": "TASK_STATE_COMPLETED",
                "timestamp": _now_iso(),
            },
            "artifacts": [
                {
                    "artifactId": str(uuid.uuid4()),
                    "name": "delivery-receipt",
                    "description": "AgentNetwork point-to-point delivery receipt",
                    "parts": [
                        {
                            "data": {
                                "delivered": True,
                                "messageId": message_id,
                                "targetAgentId": target_id,
                            },
                            "mediaType": "application/json",
                        }
                    ],
                }
            ],
            "history": [message],
            "metadata": {
                "fromAgentId": source_id,
                "targetAgentId": target_id,
                "traceId": trace_id,
            },
        }
        with self._task_lock:
            self._tasks[task_id] = task
        return {"task": task}

    def get_task(self, task_id: str) -> dict[str, Any]:
        try:
            return self.task_manager.get_task(task_id)
        except TaskManagerError:
            pass
        with self._task_lock:
            task = self._tasks.get(task_id)
        if task is None:
            raise CommunicationError(
                "TASK_NOT_FOUND", f"Task '{task_id}' was not found", 404
            )
        return task

    def list_tasks(
        self,
        context_id: str = "",
        status: str = "",
        page_size: int = 50,
        include_artifacts: bool = False,
    ) -> dict[str, Any]:
        persistent = self.task_manager.list_tasks(
            context_id=context_id,
            status=status,
            page_size=page_size,
            include_artifacts=include_artifacts,
        )
        page_size = max(1, min(int(page_size), 100))
        with self._task_lock:
            tasks = list(self._tasks.values())
        if context_id:
            tasks = [task for task in tasks if task.get("contextId") == context_id]
        if status:
            tasks = [
                task
                for task in tasks
                if (task.get("status") or {}).get("state") == status
            ]
        total_size = len(tasks) + persistent["totalSize"]
        selected = []
        for task in tasks[:page_size]:
            item = dict(task)
            if not include_artifacts:
                item.pop("artifacts", None)
            selected.append(item)
        return {
            "tasks": [*persistent["tasks"], *selected][:page_size],
            "nextPageToken": "",
            "pageSize": page_size,
            "totalSize": total_size,
        }

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        try:
            return self.task_manager.cancel_task(task_id)
        except TaskManagerError as exc:
            if exc.code != "TASK_NOT_FOUND":
                raise CommunicationError(exc.code, str(exc), 409) from exc
        task = self.get_task(task_id)
        state = (task.get("status") or {}).get("state")
        if state in {
            "TASK_STATE_COMPLETED",
            "TASK_STATE_FAILED",
            "TASK_STATE_CANCELED",
            "TASK_STATE_REJECTED",
        }:
            raise CommunicationError(
                "TASK_NOT_CANCELABLE",
                f"Task '{task_id}' is already terminal",
                409,
            )
        task["status"] = {
            "state": "TASK_STATE_CANCELED",
            "timestamp": _now_iso(),
        }
        return task

    def clear_tasks(self) -> None:
        with self._task_lock:
            self._tasks.clear()
        self.task_manager.clear()

    def receive_task_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.task_manager.apply_callback(payload)
        except TaskManagerError as exc:
            raise CommunicationError(exc.code, str(exc), 404) from exc

    def cancel_remote_task(self, task_id: str) -> dict[str, Any]:
        try:
            record = self.task_manager.get_record(task_id)
            target_id = record["target_agent_id"]
            interface_url = self._resolve_interface(target_id)
            response = self._session.post(
                f"{interface_url}/tasks/{task_id}:cancel",
                json={"id": task_id},
                headers={
                    "A2A-Version": A2A_PROTOCOL_VERSION,
                    "Content-Type": A2A_MEDIA_TYPE,
                    "Accept": A2A_MEDIA_TYPE,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            task = response.json()
            state = (task.get("status") or {}).get("state", "TASK_STATE_CANCELED")
            return self.task_manager.transition(task_id, state)
        except Exception as exc:
            raise CommunicationError("TASK_CANCEL_FAILED", str(exc), 409) from exc

    def agent_card(
        self,
        base_url: str,
        skills: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        interface_url = f"{base_url.rstrip('/')}/a2a/v1"
        skill_items = [
            {
                "id": str(skill),
                "name": str(skill),
                "description": f"AgentNetwork skill: {skill}",
                "tags": [str(skill)],
            }
            for skill in dict.fromkeys(skills or [])
        ]
        return {
            "name": self.agent_name or self.agent_id,
            "description": f"AgentNetwork {self.agent_role} Agent",
            "supportedInterfaces": [
                {
                    "url": interface_url,
                    "protocolBinding": "HTTP+JSON",
                    "protocolVersion": A2A_PROTOCOL_VERSION,
                }
            ],
            "version": "1.0.0",
            "capabilities": {
                "streaming": False,
                "pushNotifications": True,
                "extendedAgentCard": False,
            },
            "securitySchemes": {},
            "securityRequirements": [],
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain", "application/json"],
            "skills": skill_items,
        }
