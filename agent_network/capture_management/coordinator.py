from __future__ import annotations

import threading
from typing import Optional

import requests

from .manager import CaptureManager
from .models import CaptureSession, CaptureTarget


class AgentHttpCaptureManager(CaptureManager):
    """CaptureManager transport for the current Agent runtime HTTP contract."""

    @staticmethod
    def _start_target(session: CaptureSession, target: CaptureTarget) -> dict:
        response = requests.post(
            f"{target.runtime_url}/capture/start",
            json={
                "capture_id": session.capture_id,
                "session_id": session.session_id,
                "trace_id": session.trace_id,
                "agent_id": target.agent_id,
                "runtime_container": target.container_name,
                "runtime_container_id": target.container_id,
                "runtime_ip": target.runtime_ip,
                "interface": session.config.interface,
                "network_profiles": target.details.get("network_profiles", []),
            },
            timeout=10,
        )
        body = response.json() if response.content else {}
        if response.status_code != 200:
            raise RuntimeError(body.get("detail") or body.get("error") or f"HTTP {response.status_code}")
        return body

    @staticmethod
    def _stop_target(session: CaptureSession, target: CaptureTarget, reason: str) -> dict:
        response = requests.post(
            f"{target.runtime_url}/capture/stop",
            json={"capture_id": session.capture_id, "reason": reason},
            timeout=max(10, int(session.config.stop_timeout_seconds) + 5),
        )
        body = response.json() if response.content else {}
        if response.status_code != 200:
            raise RuntimeError(body.get("detail") or body.get("error") or f"HTTP {response.status_code}")
        return body

    def check_health(self, capture_id: str) -> CaptureSession:
        session = self.get_session(capture_id)
        if session.state.value != "running":
            return session
        failures = []
        for target in session.targets.values():
            try:
                response = requests.get(f"{target.runtime_url}/capture/status", timeout=5)
                body = response.json() if response.content else {}
                if response.status_code != 200:
                    raise RuntimeError(body.get("detail") or f"HTTP {response.status_code}")
                self._apply_target_result(target, body)
                if target.state.value != "running":
                    failures.append(target.agent_id)
            except Exception as exc:
                from .models import CaptureState
                target.state = CaptureState.INCOMPLETE
                target.error = str(exc)
                failures.append(target.agent_id)
        if failures:
            from .models import CaptureState
            session.state = CaptureState.INCOMPLETE
            session.error = "unhealthy targets: " + ", ".join(sorted(failures))
            session.termination_reason = "capture_incomplete"
        self._persist(session)
        return session


_coordinator: Optional[AgentHttpCaptureManager] = None
_lock = threading.Lock()


def get_capture_coordinator() -> AgentHttpCaptureManager:
    global _coordinator
    with _lock:
        if _coordinator is None:
            _coordinator = AgentHttpCaptureManager()
        return _coordinator
