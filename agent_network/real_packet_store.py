import subprocess
from pathlib import Path
from typing import Optional

PCAP_ROOT = Path("data/pcap")


def _pcap_files(session_id: str = "", agent_id: Optional[str] = None):
    root = PCAP_ROOT / session_id if session_id else PCAP_ROOT
    if not root.exists():
        return []
    files = sorted(root.rglob("*.pcap"))
    if agent_id:
        files = [p for p in files if p.stem == agent_id]
    return files


def _read_lines(pcap_path: Path, limit: int = 200):
    cmd = ["tcpdump", "-tttt", "-nn", "-r", str(pcap_path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except Exception as exc:
        return [f"pcap_parse_error {pcap_path}: {exc}"]

    stderr = (proc.stderr or "").strip()
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines and stderr:
        lines = [f"pcap_parse_warning {pcap_path}: {stderr}"]
    return lines[-limit:]


def query_packets(session_id: str = "", agent_id: Optional[str] = None, limit: int = 100):
    packets = []
    for pcap in _pcap_files(session_id=session_id, agent_id=agent_id):
        for line in _read_lines(pcap, limit=limit):
            packets.append({
                "capture_source": "tcpdump_pcap",
                "agent_id": pcap.stem,
                "pcap": str(pcap),
                "line": line,
            })
    return packets[-limit:]


def wireshark_lines(session_id: str = "", agent_id: Optional[str] = None, limit: int = 100):
    return [p["line"] for p in query_packets(session_id=session_id, agent_id=agent_id, limit=limit)]


def packet_stats(session_id: str = ""):
    files = _pcap_files(session_id=session_id)
    return {
        "capture_source": "tcpdump_pcap",
        "pcap_files": len(files),
        "files": [str(p) for p in files],
    }
