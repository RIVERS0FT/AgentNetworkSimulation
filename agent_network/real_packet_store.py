"""Read and summarize real tcpdump PCAP files produced by Agent containers."""

import json
import os
import re
import struct
import subprocess
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


PCAP_ROOT = Path(os.environ.get("PCAP_DIR", "data/pcap"))
_LINE_RE = re.compile(
    r"^(?P<timestamp>(?:\d{4}-\d{2}-\d{2}\s+\S+)|(?:\d+(?:\.\d+)?))\s+"
    r"(?P<ip_version>IP6?)\s+(?P<src>\S+)\s+>\s+(?P<dst>\S+):\s*(?P<details>.*)$"
)
_LENGTH_RE = re.compile(r"\blength\s+(?P<length>\d+)\b")
_FLAGS_RE = re.compile(r"\bFlags\s+\[(?P<flags>[^]]*)\]")


def _pcap_files(session_id: str = "", agent_id: Optional[str] = None):
    base = PCAP_ROOT.resolve()
    root = (PCAP_ROOT / session_id).resolve() if session_id else base
    try:
        root.relative_to(base)
    except ValueError:
        return []
    if not root.exists():
        return []
    files = sorted(root.rglob("*.pcap"))
    if agent_id:
        files = [p for p in files if p.stem == agent_id]
    return files


def _load_manifest(pcap_path: Path) -> dict:
    path = pcap_path.with_name(f"{pcap_path.stem}.manifest.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _read_lines(pcap_path: Path, limit: int = 1000):
    """Read the newest decoded packets with bounded memory.

    tcpdump still scans the file to reach the newest records, but Python never
    materializes unbounded stdout for a large capture.
    """
    # Epoch timestamps avoid container/server timezone ambiguity.
    cmd = ["tcpdump", "-tt", "-nn", "-r", str(pcap_path)]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        lines = deque(maxlen=max(1, limit))
        scanned = 0
        for line in proc.stdout or []:
            if line.strip():
                lines.append(line.rstrip("\r\n"))
                scanned += 1
        proc.wait(timeout=30)
        stderr = (proc.stderr.read() if proc.stderr else "").strip()
    except Exception as exc:
        try:
            proc.kill()
        except Exception:
            pass
        return [], f"pcap_parse_error {pcap_path}: {exc}", 0
    error = stderr if proc.returncode != 0 else ""
    return list(lines), error, scanned


def _endpoint(value: str) -> tuple[str, int]:
    host, separator, port = value.rpartition(".")
    if separator and port.isdigit():
        return host, int(port)
    return value, 0


def _timestamp(value: str) -> tuple[str, float]:
    try:
        epoch = float(value)
        return datetime.fromtimestamp(epoch, timezone.utc).isoformat(), epoch
    except ValueError:
        pass
    try:
        local = datetime.fromisoformat(value.replace(" ", "T"))
        if local.tzinfo is None:
            local = local.replace(tzinfo=timezone(timedelta(hours=8)))
        return local.astimezone(timezone.utc).isoformat(), local.timestamp()
    except ValueError:
        return value, 0.0


def _parse_line(line: str, pcap_path: Path, manifest: dict, identities: dict = None) -> dict:
    record = {
        "capture_source": "tcpdump_pcap",
        "agent_id": manifest.get("agent_id") or pcap_path.stem,
        "runtime_container": manifest.get("runtime_container", ""),
        "session_id": manifest.get("session_id") or pcap_path.parent.name,
        "trace_id": manifest.get("trace_id", ""),
        "pcap": str(pcap_path),
        "line": line,
        "raw": line,
    }
    match = _LINE_RE.match(line)
    if not match:
        record.update({"parsed": False, "protocol": "unknown", "ip_payload_bytes": 0})
        return record

    values = match.groupdict()
    timestamp, timestamp_epoch = _timestamp(values["timestamp"])
    src_ip, src_port = _endpoint(values["src"])
    dst_ip, dst_port = _endpoint(values["dst"])
    identities = identities or {}
    own_ip = manifest.get("runtime_ip", "")
    if own_ip and src_ip == own_ip:
        direction = "outbound"
    elif own_ip and dst_ip == own_ip:
        direction = "inbound"
    else:
        direction = "observed"
    src_agent = identities.get(src_ip, "")
    dst_agent = identities.get(dst_ip, "")
    # Non-peer includes LLM/MCP/Internet and container infrastructure such as DNS.
    # Do not label it "external" without an authoritative network inventory.
    traffic_class = "agent_peer" if src_agent and dst_agent else "agent_non_peer"
    details = values["details"]
    length_match = _LENGTH_RE.search(details)
    flags_match = _FLAGS_RE.search(details)
    if flags_match:
        protocol = "TCP"
    elif details.startswith("UDP") or " UDP," in details:
        protocol = "UDP"
    elif "ICMP" in details:
        protocol = "ICMP"
    else:
        protocol = "IP"
    record.update({
        "parsed": True,
        "timestamp": timestamp,
        "timestamp_raw": values["timestamp"],
        "timestamp_epoch": timestamp_epoch,
        "ip_version": values["ip_version"],
        "protocol": protocol,
        "src_ip": src_ip,
        "src_port": src_port,
        "dst_ip": dst_ip,
        "dst_port": dst_port,
        "direction": direction,
        "traffic_class": traffic_class,
        "src_agent": src_agent,
        "dst_agent": dst_agent,
        "tcp_flags": flags_match.group("flags") if flags_match else "",
        # tcpdump's `length` here is the IP payload length, not on-wire frame size.
        "ip_payload_bytes": int(length_match.group("length")) if length_match else 0,
    })
    return record


def _pcap_metadata(path: Path) -> dict:
    """Count records and bytes directly from classic PCAP record headers."""
    result = {
        "pcap": str(path),
        "file_bytes": path.stat().st_size if path.is_file() else 0,
        "packet_count": 0,
        "captured_bytes": 0,
        "wire_bytes": 0,
        "first_packet_at": "",
        "last_packet_at": "",
        "valid_pcap": False,
    }
    try:
        with path.open("rb") as stream:
            global_header = stream.read(24)
            if len(global_header) != 24:
                return result
            magic = global_header[:4]
            formats = {
                b"\xd4\xc3\xb2\xa1": ("<", 1_000_000),
                b"\xa1\xb2\xc3\xd4": (">", 1_000_000),
                b"\x4d\x3c\xb2\xa1": ("<", 1_000_000_000),
                b"\xa1\xb2\x3c\x4d": (">", 1_000_000_000),
            }
            if magic not in formats:
                return result
            endian, fraction_scale = formats[magic]
            first_timestamp = None
            last_timestamp = None
            while True:
                packet_header = stream.read(16)
                if not packet_header:
                    result["valid_pcap"] = True
                    break
                if len(packet_header) != 16:
                    break
                seconds, fraction, captured_length, original_length = struct.unpack(
                    f"{endian}IIII", packet_header
                )
                payload = stream.read(captured_length)
                if len(payload) != captured_length:
                    break
                timestamp = seconds + (fraction / fraction_scale)
                first_timestamp = timestamp if first_timestamp is None else first_timestamp
                last_timestamp = timestamp
                result["packet_count"] += 1
                result["captured_bytes"] += captured_length
                result["wire_bytes"] += original_length
            if first_timestamp is not None:
                result["first_packet_at"] = datetime.fromtimestamp(first_timestamp, timezone.utc).isoformat()
                result["last_packet_at"] = datetime.fromtimestamp(last_timestamp, timezone.utc).isoformat()
    except OSError as exc:
        result["error"] = str(exc)
    return result


def query_packets(session_id: str = "", agent_id: Optional[str] = None, limit: int = 100):
    packets = []
    errors = []
    all_pcaps = _pcap_files(session_id=session_id)
    identities = {}
    for pcap in all_pcaps:
        manifest = _load_manifest(pcap)
        if manifest.get("runtime_ip") and manifest.get("agent_id"):
            identities[manifest["runtime_ip"]] = manifest["agent_id"]
    selected_pcaps = [pcap for pcap in all_pcaps if not agent_id or pcap.stem == agent_id]
    for pcap in selected_pcaps:
        manifest = _load_manifest(pcap)
        lines, error, _ = _read_lines(pcap, limit=limit)
        packets.extend(_parse_line(line, pcap, manifest, identities) for line in lines)
        if error:
            errors.append({
                "capture_source": "tcpdump_pcap",
                "agent_id": manifest.get("agent_id") or pcap.stem,
                "pcap": str(pcap),
                "parsed": False,
                "error": error,
            })
    packets.sort(key=lambda item: item.get("timestamp", ""))
    return (packets + errors)[-limit:]


def wireshark_lines(session_id: str = "", agent_id: Optional[str] = None, limit: int = 100):
    return [p.get("raw") or p.get("error", "") for p in query_packets(session_id, agent_id, limit)]


def pcap_path(session_id: str, agent_id: str) -> Optional[Path]:
    files = _pcap_files(session_id=session_id, agent_id=agent_id)
    return files[0] if len(files) == 1 else None


def analyze_packets(session_id: str = "", agent_id: Optional[str] = None, max_packets: int = 100_000):
    all_pcaps = _pcap_files(session_id=session_id)
    identities = {}
    for pcap in all_pcaps:
        manifest = _load_manifest(pcap)
        if manifest.get("runtime_ip") and manifest.get("agent_id"):
            identities[manifest["runtime_ip"]] = manifest["agent_id"]

    selected = [pcap for pcap in all_pcaps if not agent_id or pcap.stem == agent_id]
    protocols = Counter()
    directions = Counter()
    traffic_classes = Counter()
    endpoints = Counter()
    flows = {}
    payload_bytes = 0
    scanned = 0
    analyzed = 0
    retained = 0
    errors = []
    per_file_limit = max(1, max_packets // max(1, len(selected)))

    for pcap in selected:
        manifest = _load_manifest(pcap)
        lines, error, file_scanned = _read_lines(pcap, limit=per_file_limit)
        scanned += file_scanned
        retained += len(lines)
        if error:
            errors.append({"pcap": str(pcap), "error": error})
        for line in lines:
            packet = _parse_line(line, pcap, manifest, identities)
            if not packet.get("parsed"):
                continue
            analyzed += 1
            protocols[packet["protocol"]] += 1
            directions[packet["direction"]] += 1
            traffic_classes[packet["traffic_class"]] += 1
            payload_bytes += packet["ip_payload_bytes"]
            if packet["direction"] == "outbound":
                endpoint = f"{packet['dst_ip']}:{packet['dst_port']}"
            elif packet["direction"] == "inbound":
                endpoint = f"{packet['src_ip']}:{packet['src_port']}"
            else:
                endpoint = f"{packet['dst_ip']}:{packet['dst_port']}"
            endpoints[endpoint] += 1
            left = f"{packet['src_ip']}:{packet['src_port']}"
            right = f"{packet['dst_ip']}:{packet['dst_port']}"
            flow_endpoints = tuple(sorted((left, right)))
            flow_key = (packet["protocol"], *flow_endpoints)
            flow = flows.setdefault(flow_key, {
                "protocol": packet["protocol"],
                "endpoint_a": flow_endpoints[0],
                "endpoint_b": flow_endpoints[1],
                "packets": 0,
                "ip_payload_bytes": 0,
                "first_timestamp_epoch": packet.get("timestamp_epoch", 0),
                "last_timestamp_epoch": packet.get("timestamp_epoch", 0),
            })
            flow["packets"] += 1
            flow["ip_payload_bytes"] += packet["ip_payload_bytes"]
            timestamp_epoch = packet.get("timestamp_epoch", 0)
            if timestamp_epoch:
                if not flow["first_timestamp_epoch"] or timestamp_epoch < flow["first_timestamp_epoch"]:
                    flow["first_timestamp_epoch"] = timestamp_epoch
                if timestamp_epoch > flow["last_timestamp_epoch"]:
                    flow["last_timestamp_epoch"] = timestamp_epoch

    return {
        "capture_source": "tcpdump_pcap",
        "session_id": session_id,
        "agent_id": agent_id or "",
        "pcap_files": len(selected),
        "packets_scanned": scanned,
        "packets_analyzed": analyzed,
        "sampled": scanned > retained,
        "sample_limit": max_packets,
        "ip_payload_bytes": payload_bytes,
        "by_protocol": dict(protocols),
        "by_direction": dict(directions),
        "by_traffic_class": dict(traffic_classes),
        "top_endpoints": [
            {"endpoint": endpoint, "packets": count}
            for endpoint, count in endpoints.most_common(50)
        ],
        "top_flows": sorted(
            flows.values(),
            key=lambda flow: (flow["ip_payload_bytes"], flow["packets"]),
            reverse=True,
        )[:100],
        "errors": errors,
        "aggregation_scope": "per_agent_observations",
        "aggregation_note": "Agent-to-Agent packets are visible in both endpoint PCAPs and are not deduplicated.",
    }


def packet_stats(session_id: str = ""):
    files = []
    totals = {"packet_count": 0, "captured_bytes": 0, "wire_bytes": 0, "file_bytes": 0}
    for pcap in _pcap_files(session_id=session_id):
        metadata = _pcap_metadata(pcap)
        metadata["agent_id"] = _load_manifest(pcap).get("agent_id") or pcap.stem
        files.append(metadata)
        for key in totals:
            totals[key] += metadata[key]
    return {
        "capture_source": "tcpdump_pcap",
        "aggregation_scope": "per_agent_observations",
        "aggregation_note": "Agent-to-Agent packets are visible in both endpoint PCAPs and are not deduplicated.",
        "session_id": session_id,
        "pcap_files": len(files),
        **totals,
        "files": files,
    }
