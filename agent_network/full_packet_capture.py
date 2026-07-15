"""Real packet capture inside an Agent container network namespace."""
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
from agent_network.file_management import get_file_manager, stable_resource_id
_capture_process: Optional[subprocess.Popen] = None
_capture_lock = threading.Lock()
_capture_metadata: dict = {}
_capture_watchdog: Optional[threading.Thread] = None

def _safe(value: str) -> str:
    return ''.join((c if c.isalnum() or c in ('-', '_') else '_' for c in str(value or ''))) or 'unknown'

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

def _max_capture_bytes() -> int:
    try:
        return max(0, int(os.environ.get('PCAP_MAX_BYTES', str(1024 * 1024 * 1024))))
    except ValueError:
        return 1024 * 1024 * 1024

def _control_plane_filter(server_url: str) -> str:
    if os.environ.get('AGENT_CAPTURE_INCLUDE_CONTROL_PLANE', '0') == '1':
        return ''
    hostname = urlparse(server_url or '').hostname
    if not hostname:
        return ''
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(hostname, None)})
    except OSError:
        addresses = []
    safe_addresses = [addr for addr in addresses if addr and '%' not in addr]
    return ' and '.join((f'not host {address}' for address in safe_addresses))

def _public_metadata(data: dict) -> dict:
    return {key: value for key, value in data.items() if not key.startswith('_')}

def _manifest_resource_id(session_id: str, agent_id: str) -> str:
    return stable_resource_id('capture', session_id, agent_id, 'manifest')

def _pcap_resource_id(session_id: str, agent_id: str) -> str:
    return stable_resource_id('capture', session_id, agent_id, 'pcap')

def _write_manifest(data: dict) -> None:
    manager = get_file_manager()
    manager.write_json(_public_metadata(data), owner_type='capture_session', owner_id=data['session_id'], resource_type='capture_manifest', root_name='pcap', relative_path=f"{data['session_id']}/{data['agent_id']}.manifest.json", logical_name=f"{data['agent_id']}.manifest.json", resource_id=data['manifest_resource_id'], overwrite=True)

def _refresh_pcap(*, compute_sha256: bool=False) -> tuple[int, str]:
    manager = get_file_manager()
    resource_id = _capture_metadata.get('pcap_resource_id', '')
    if not resource_id:
        return (0, '')
    try:
        resource = manager.refresh(resource_id, compute_sha256=compute_sha256)
        return (resource.size_bytes, resource.sha256)
    except Exception:
        return (0, '')

def _watch_capture(process: subprocess.Popen, pcap_path: Path, max_bytes: int) -> None:
    while process.poll() is None:
        try:
            current_bytes = pcap_path.stat().st_size if pcap_path.exists() else 0
            if max_bytes > 0 and current_bytes > max_bytes:
                _capture_metadata['limit_reached'] = True
                _capture_metadata['capture_error'] = f'PCAP exceeded configured limit of {max_bytes} bytes'
                _write_manifest({**_capture_metadata, 'status': 'error', 'pcap_bytes': current_bytes, 'stopped_at': _now_iso()})
                process.send_signal(signal.SIGTERM)
                return
        except OSError:
            pass
        time.sleep(1)

def capture_status() -> dict:
    process = _capture_process
    if not process:
        return {'status': 'not_running'}
    pcap_bytes, _ = _refresh_pcap(compute_sha256=False)
    return {'status': 'running' if process.poll() is None else 'error', **_public_metadata(_capture_metadata), 'pid': process.pid, 'returncode': process.poll(), 'pcap_bytes': pcap_bytes}

def start_full_capture(agent_id: str, session_id: str='', pcap_dir: str='/app/data/pcap', interface: str='any', runtime_container: str='', runtime_container_id: str='', runtime_ip: str='', trace_id: str='', server_url: str='', network_profiles: list=None):
    """Capture real Agent traffic and register PCAP plus attribution manifest."""
    global _capture_process, _capture_metadata, _capture_watchdog
    if os.environ.get('LOG_FULL_PCAP', '1') != '1':
        return {'status': 'disabled', 'reason': 'LOG_FULL_PCAP!=1'}
    with _capture_lock:
        if _capture_process and _capture_process.poll() is None:
            return {'status': 'running', **_public_metadata(_capture_metadata), 'pid': _capture_process.pid}
        manager = get_file_manager()
        configured_root = manager.root_path('pcap')
        requested_root = Path(pcap_dir).resolve()
        if requested_root != configured_root:
            return {'status': 'error', 'error': 'pcap_dir must match the unified managed pcap root'}
        logical_agent_id = _safe(agent_id or 'agent')
        runtime_container = _safe(runtime_container or os.environ.get('AGENT_ID', 'unknown'))
        session_id = _safe(session_id or datetime.now().strftime('%Y%m%d_%H%M%S'))
        manager.ensure_directory(owner_type='capture_session', owner_id=session_id, resource_type='capture_session_directory', root_name='pcap', relative_path=session_id, logical_name=session_id, resource_id=stable_resource_id('capture', session_id, 'directory'))
        pcap_relative = f'{session_id}/{logical_agent_id}.pcap'
        pcap_path = manager.resolve_path('pcap', pcap_relative)
        capture_filter = _control_plane_filter(server_url or os.environ.get('SERVER_URL', ''))
        cmd = ['tcpdump', '-i', interface, '-nn', '-s', '0', '-U', '-w', str(pcap_path)]
        if capture_filter:
            cmd.append(capture_filter)
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        except (FileNotFoundError, PermissionError, OSError) as exc:
            return {'status': 'error', 'error': str(exc)}
        time.sleep(0.1)
        if process.poll() is not None:
            stderr = (process.stderr.read() if process.stderr else '').strip()
            return {'status': 'error', 'error': stderr or f'tcpdump exited with {process.returncode}', 'returncode': process.returncode}
        pcap_id = _pcap_resource_id(session_id, logical_agent_id)
        manager.register_existing(owner_type='capture_session', owner_id=session_id, resource_type='pcap', root_name='pcap', relative_path=pcap_relative, logical_name=f'{logical_agent_id}.pcap', media_type='application/vnd.tcpdump.pcap', resource_id=pcap_id, upsert=True)
        manifest_id = _manifest_resource_id(session_id, logical_agent_id)
        _capture_process = process
        _capture_metadata = {'agent_id': logical_agent_id, 'runtime_container': runtime_container, 'runtime_container_id': runtime_container_id, 'runtime_ip': runtime_ip, 'backend': os.environ.get('AGENT_BACKEND', ''), 'session_id': session_id, 'trace_id': trace_id, 'pcap_resource_id': pcap_id, 'manifest_resource_id': manifest_id, 'interface': interface, 'capture_filter': capture_filter, 'control_plane_included': not bool(capture_filter), 'started_at': _now_iso(), 'max_bytes': _max_capture_bytes(), 'network_profiles': network_profiles or [], '_pcap_path': str(pcap_path)}
        _write_manifest({**_capture_metadata, 'status': 'running'})
        _capture_watchdog = threading.Thread(target=_watch_capture, args=(process, pcap_path, _capture_metadata['max_bytes']), daemon=True)
        _capture_watchdog.start()
        return {'status': 'started', **_public_metadata(_capture_metadata), 'pid': process.pid}

def stop_full_capture():
    global _capture_process, _capture_metadata, _capture_watchdog
    with _capture_lock:
        if not _capture_process:
            return {'status': 'not_running'}
        if _capture_process.poll() is None:
            _capture_process.send_signal(signal.SIGTERM)
            try:
                _capture_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _capture_process.kill()
                _capture_process.wait(timeout=2)
        rc = _capture_process.returncode
        try:
            stderr = (_capture_process.stderr.read() if _capture_process.stderr else '').strip()
        except Exception:
            stderr = ''
        pcap_bytes, pcap_sha256 = _refresh_pcap(compute_sha256=True)
        pcap_valid = pcap_bytes >= 24
        result = {'status': 'stopped' if rc in (0, None) and pcap_valid and (not _capture_metadata.get('capture_error')) else 'error', **_capture_metadata, 'returncode': rc, 'pcap_bytes': pcap_bytes, 'pcap_valid': pcap_valid, 'stopped_at': _now_iso()}
        if pcap_valid and os.environ.get('PCAP_SHA256', '1') == '1':
            result['sha256'] = pcap_sha256
        if not pcap_valid:
            result['error'] = 'pcap file is missing or does not contain a complete global header'
        elif _capture_metadata.get('capture_error'):
            result['error'] = _capture_metadata['capture_error']
        if stderr:
            result['tcpdump_summary'] = stderr[-1000:]
        _write_manifest(result)
        public_result = _public_metadata(result)
        _capture_process = None
        _capture_metadata = {}
        _capture_watchdog = None
        return public_result
