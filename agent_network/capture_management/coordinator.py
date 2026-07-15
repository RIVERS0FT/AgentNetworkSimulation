from __future__ import annotations

import threading
from typing import Iterable, Optional

import requests

from .manager import CaptureManager
from .models import CaptureConfig, CaptureSession, CaptureState, CaptureTarget
from .projection import PacketProjectionService


class AgentHttpCaptureManager(CaptureManager):
    """CaptureManager transport for the Agent runtime HTTP contract."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.projection = PacketProjectionService(self.repository.files)

    def create_session(
        self,
        *,
        simulation_id: str,
        session_id: str,
        trace_id: str,
        targets: Iterable[dict],
        config: Optional[CaptureConfig] = None,
        capture_id: str = "",
    ) -> CaptureSession:
        # The current Agent HTTP adapter receives session_id as its distributed
        # capture identifier. Keep one authoritative identifier until the Agent
        # endpoint itself is moved into capture_management.
        capture_id = capture_id or session_id
        if capture_id != session_id:
            raise ValueError("capture_id must equal session_id for Agent HTTP capture transport")
        return super().create_session(
            simulation_id=simulation_id,
            session_id=session_id,
            trace_id=trace_id,
            targets=targets,
            config=config,
            capture_id=capture_id,
        )

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
        if session.state != CaptureState.RUNNING:
            return session
        failures = []
        for target in session.targets.values():
            try:
                response = requests.get(f"{target.runtime_url}/capture/status", timeout=5)
                body = response.json() if response.content else {}
                if response.status_code != 200:
                    raise RuntimeError(body.get("detail") or f"HTTP {response.status_code}")
                self._apply_target_result(target, body)
                if target.state != CaptureState.RUNNING:
                    failures.append(target.agent_id)
            except Exception as exc:
                target.state = CaptureState.INCOMPLETE
                target.error = str(exc)
                failures.append(target.agent_id)
        if failures:
            session.state = CaptureState.INCOMPLETE
            session.error = "unhealthy targets: " + ", ".join(sorted(failures))
            session.termination_reason = "capture_incomplete"
        self._persist(session)
        return session

    def stop_session(self, capture_id: str, reason: str = "requested") -> CaptureSession:
        session = super().stop_session(capture_id, reason)
        if session.config.projection_mode == "finalize":
            try:
                projection = self.projection.project(session)
                session.projection_state = projection.get("status", "failed")
                if projection.get("status") != "complete":
                    session.state = CaptureState.INCOMPLETE
                    session.error = session.error or "network log projection incomplete"
            except Exception as exc:
                session.projection_state = "failed"
                session.state = CaptureState.INCOMPLETE
                session.error = session.error or f"network log projection failed: {exc}"
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
