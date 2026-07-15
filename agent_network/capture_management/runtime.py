from __future__ import annotations

import os
import signal
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .models import CaptureConfig, CaptureState
from .repository import CaptureRepository


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _safe(value: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(value or "")) or "unknown"


class CaptureRuntime:
    """The single tcpdump owner inside one Agent network namespace."""

    def __init__(self, repository: Optional[CaptureRepository] = None) -> None:
        self.repository = repository or CaptureRepository()
        self._lock = threading.RLock()
        self._process: Optional[subprocess.Popen] = None
        self._metadata: dict = {}
        self._watchdog: Optional[threading.Thread] = None

    @staticmethod
    def _control_plane_filter(server_url: str, include_control_plane: bool) -> str:
        if include_control_plane:
            return ""
        hostname = urlparse(server_url or "").hostname
        if not hostname:
            return ""
        try:
            addresses = sorted({item[4][0] for item in socket.getaddrinfo(hostname, None)})
        except OSError:
            addresses = []
        return " and ".join(f"not host {address}" for address in addresses if address and "%" not in address)

    def _public(self, value: dict) -> dict:
        return {key: item for key, item in value.items() if not key.startswith("_")}

    def _write_manifest(self, value: dict) -> None:
        self.repository.write_target_manifest(
            value["capture_id"], value["session_id"], value["agent_id"], self._public(value)
        )

    def _watch(self, process: subprocess.Popen, pcap_path: Path, max_bytes: int) -> None:
        while process.poll() is None:
            try:
                current_bytes = pcap_path.stat().st_size if pcap_path.exists() else 0
                if max_bytes > 0 and current_bytes > max_bytes:
                    with self._lock:
                        self._metadata["limit_reached"] = True
                        self._metadata["capture_error"] = f"PCAP exceeded configured limit of {max_bytes} bytes"
                        self._metadata["state"] = CaptureState.INCOMPLETE.value
                        self._metadata["captured_bytes"] = current_bytes
                        self._metadata["stopped_at"] = _now_iso()
                        self._write_manifest(self._metadata)
                    process.send_signal(signal.SIGTERM)
                    return
            except OSError:
                pass
            time.sleep(1)

    def start(
        self,
        *,
        capture_id: str,
        session_id: str,
        agent_id: str,
        config: CaptureConfig,
        runtime_container: str = "",
        runtime_container_id: str = "",
        runtime_ip: str = "",
        trace_id: str = "",
        server_url: str = "",
        network_profiles: Optional[list] = None,
    ) -> dict:
        config.validate()
        capture_id = _safe(capture_id)
        session_id = _safe(session_id)
        agent_id = _safe(agent_id)
        with self._lock:
            if self._process and self._process.poll() is None:
                if self._metadata.get("capture_id") == capture_id:
                    return {"status": "running", **self._public(self._metadata), "pid": self._process.pid}
                return {
                    "status": "conflict",
                    "error": f"capture {self._metadata.get('capture_id')} is already running",
                }

            self.repository.ensure_session(capture_id, session_id)
            root = self.repository.files.root_path("pcap")
            relative = f"{session_id}/{agent_id}.pcap"
            pcap_path = self.repository.files.resolve_path("pcap", relative)
            pcap_path.parent.mkdir(parents=True, exist_ok=True)
            capture_filter = config.bpf_filter or self._control_plane_filter(server_url, config.include_control_plane)
            command = [
                "tcpdump", "-i", config.interface, "-nn", "-s", str(config.snap_length), "-U", "-w", str(pcap_path)
            ]
            if capture_filter:
                command.append(capture_filter)
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except (FileNotFoundError, PermissionError, OSError) as exc:
                return {"status": "error", "error": str(exc)}
            time.sleep(0.1)
            if process.poll() is not None:
                stderr = (process.stderr.read() if process.stderr else "").strip()
                return {
                    "status": "error",
                    "error": stderr or f"tcpdump exited with {process.returncode}",
                    "returncode": process.returncode,
                }

            pcap = self.repository.register_pcap(capture_id, session_id, agent_id)
            self._process = process
            self._metadata = {
                "capture_id": capture_id,
                "session_id": session_id,
                "trace_id": trace_id,
                "agent_id": agent_id,
                "runtime_container": _safe(runtime_container or os.environ.get("AGENT_ID", "unknown")),
                "runtime_container_id": runtime_container_id,
                "runtime_ip": runtime_ip,
                "backend": os.environ.get("AGENT_BACKEND", ""),
                "state": CaptureState.RUNNING.value,
                "interface": config.interface,
                "capture_filter": capture_filter,
                "control_plane_included": config.include_control_plane,
                "started_at": _now_iso(),
                "max_bytes": config.max_bytes,
                "network_profiles": network_profiles or [],
                "pcap_resource_id": pcap.resource_id,
                "manifest_resource_id": self.repository.manifest_resource_id(capture_id, agent_id),
                "_pcap_path": str(pcap_path),
            }
            self._write_manifest(self._metadata)
            self._watchdog = threading.Thread(
                target=self._watch,
                args=(process, pcap_path, config.max_bytes),
                daemon=True,
            )
            self._watchdog.start()
            return {"status": "started", **self._public(self._metadata), "pid": process.pid}

    def status(self, capture_id: str = "") -> dict:
        with self._lock:
            if not self._process:
                return {"status": "not_running", "capture_id": capture_id}
            if capture_id and self._metadata.get("capture_id") != capture_id:
                return {"status": "not_found", "capture_id": capture_id}
            try:
                resource = self.repository.files.refresh(
                    self._metadata["pcap_resource_id"], compute_sha256=False
                )
                captured_bytes = resource.size_bytes
            except Exception:
                captured_bytes = 0
            state = CaptureState.RUNNING.value if self._process.poll() is None else CaptureState.INCOMPLETE.value
            return {
                "status": state,
                **self._public(self._metadata),
                "pid": self._process.pid,
                "returncode": self._process.poll(),
                "captured_bytes": captured_bytes,
            }

    def stop(self, capture_id: str = "", reason: str = "requested") -> dict:
        with self._lock:
            if not self._process:
                return {"status": "not_running", "capture_id": capture_id}
            if capture_id and self._metadata.get("capture_id") != capture_id:
                return {"status": "not_found", "capture_id": capture_id}
            process = self._process
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            try:
                stderr = (process.stderr.read() if process.stderr else "").strip()
            except Exception:
                stderr = ""
            try:
                pcap = self.repository.files.refresh(
                    self._metadata["pcap_resource_id"], compute_sha256=True
                )
                captured_bytes = pcap.size_bytes
                sha256 = pcap.sha256
            except Exception:
                captured_bytes = 0
                sha256 = ""
            valid = captured_bytes >= 24
            failed = process.returncode not in (0, None) or not valid or bool(self._metadata.get("capture_error"))
            result = {
                **self._metadata,
                "state": CaptureState.INCOMPLETE.value if failed else CaptureState.STOPPED.value,
                "status": "error" if failed else "stopped",
                "returncode": process.returncode,
                "captured_bytes": captured_bytes,
                "pcap_valid": valid,
                "sha256": sha256,
                "termination_reason": reason,
                "stopped_at": _now_iso(),
            }
            if not valid:
                result["error"] = "pcap file is missing or does not contain a complete global header"
            elif self._metadata.get("capture_error"):
                result["error"] = self._metadata["capture_error"]
            if stderr:
                result["tcpdump_summary"] = stderr[-1000:]
            self._write_manifest(result)
            public = self._public(result)
            self._process = None
            self._metadata = {}
            self._watchdog = None
            return public


_runtime: Optional[CaptureRuntime] = None
_runtime_lock = threading.Lock()


def get_capture_runtime() -> CaptureRuntime:
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = CaptureRuntime()
        return _runtime
