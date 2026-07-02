"""Real packet capture inside an Agent container network namespace."""

import json
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


_capture_process: Optional[subprocess.Popen] = None
_capture_lock = threading.Lock()
_capture_metadata: dict = {}


def _safe(value: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(value or "")) or "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _control_plane_filter(server_url: str) -> str:
    """Build a BPF clause that excludes srv control/logging traffic.

    Capturing happens in the Agent namespace. Excluding the srv address keeps
    Agent-to-Agent, LLM, MCP, DNS, and their response packets while dropping
    /run, /capture, and log-ingest traffic.
    """
    if os.environ.get("AGENT_CAPTURE_INCLUDE_CONTROL_PLANE", "0") == "1":
        return ""
    hostname = urlparse(server_url or "").hostname
    if not hostname:
        return ""
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(hostname, None)})
    except OSError:
        addresses = []
    safe_addresses = [addr for addr in addresses if addr and "%" not in addr]
    if not safe_addresses:
        return ""
    return " and ".join(f"not host {address}" for address in safe_addresses)


def _write_manifest(path: Path, data: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def start_full_capture(
    agent_id: str,
    session_id: str = "",
    pcap_dir: str = "/app/data/pcap",
    interface: str = "any",
    runtime_container: str = "",
    runtime_container_id: str = "",
    runtime_ip: str = "",
    trace_id: str = "",
    server_url: str = "",
):
    """Capture real Agent traffic and write a sidecar attribution manifest."""
    global _capture_process, _capture_metadata

    if os.environ.get("LOG_FULL_PCAP", "1") != "1":
        return {"status": "disabled", "reason": "LOG_FULL_PCAP!=1"}

    with _capture_lock:
        if _capture_process and _capture_process.poll() is None:
            return {"status": "running", **_capture_metadata, "pid": _capture_process.pid}

        logical_agent_id = _safe(agent_id or "agent")
        runtime_container = _safe(runtime_container or os.environ.get("AGENT_ID", "unknown"))
        session_id = _safe(session_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
        out_dir = Path(pcap_dir) / session_id
        out_dir.mkdir(parents=True, exist_ok=True)
        pcap_path = out_dir / f"{logical_agent_id}.pcap"
        manifest_path = out_dir / f"{logical_agent_id}.manifest.json"
        capture_filter = _control_plane_filter(server_url or os.environ.get("SERVER_URL", ""))

        cmd = ["tcpdump", "-i", interface, "-nn", "-s", "0", "-U", "-w", str(pcap_path)]
        if capture_filter:
            cmd.append(capture_filter)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            return {"status": "error", "error": str(exc), "cmd": cmd}

        time.sleep(0.1)
        if process.poll() is not None:
            stderr = (process.stderr.read() if process.stderr else "").strip()
            return {
                "status": "error",
                "error": stderr or f"tcpdump exited with {process.returncode}",
                "returncode": process.returncode,
                "cmd": cmd,
            }

        _capture_process = process
        _capture_metadata = {
            "agent_id": logical_agent_id,
            "runtime_container": runtime_container,
            "runtime_container_id": runtime_container_id,
            "runtime_ip": runtime_ip,
            "backend": os.environ.get("AGENT_BACKEND", ""),
            "session_id": session_id,
            "trace_id": trace_id,
            "pcap_path": str(pcap_path),
            "manifest_path": str(manifest_path),
            "interface": interface,
            "capture_filter": capture_filter,
            "control_plane_included": not bool(capture_filter),
            "started_at": _now_iso(),
        }
        _write_manifest(manifest_path, {**_capture_metadata, "status": "running"})
        return {"status": "started", **_capture_metadata, "pid": process.pid, "cmd": cmd}


def stop_full_capture():
    global _capture_process, _capture_metadata

    with _capture_lock:
        if not _capture_process:
            return {"status": "not_running"}

        if _capture_process.poll() is None:
            _capture_process.send_signal(signal.SIGTERM)
            try:
                _capture_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _capture_process.kill()
                _capture_process.wait(timeout=2)

        rc = _capture_process.returncode
        stderr = ""
        try:
            stderr = (_capture_process.stderr.read() if _capture_process.stderr else "").strip()
        except Exception:
            pass

        pcap_path = Path(_capture_metadata.get("pcap_path", ""))
        pcap_bytes = pcap_path.stat().st_size if pcap_path.is_file() else 0
        pcap_valid = pcap_bytes >= 24
        result = {
            "status": "stopped" if rc in (0, None) and pcap_valid else "error",
            **_capture_metadata,
            "returncode": rc,
            "pcap_bytes": pcap_bytes,
            "pcap_valid": pcap_valid,
            "stopped_at": _now_iso(),
        }
        if not pcap_valid:
            result["error"] = "pcap file is missing or does not contain a complete global header"
        if stderr:
            result["tcpdump_summary"] = stderr[-1000:]
        manifest_path = Path(_capture_metadata.get("manifest_path", ""))
        if manifest_path.parent.exists():
            _write_manifest(manifest_path, result)

        _capture_process = None
        _capture_metadata = {}
        return result
