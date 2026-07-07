# Agent runtime traffic capture

The source of truth for network traffic is the PCAP written inside each Agent
container network namespace. Application JSONL events provide semantic context;
scene `traffic_log` arrays are synthetic model data and must not be mixed with
observed packet totals.

## Capture scope

By default, the capture excludes the `srv` address, so `/run`, capture control,
and log-ingest traffic do not pollute Agent runtime measurements. It retains
Agent-to-Agent, LLM, MCP, DNS, and response packets. Set
`AGENT_CAPTURE_INCLUDE_CONTROL_PLANE=1` only for control-plane debugging.

Each session contains:

```text
data/pcap/<session_id>/<logical_agent_id>.pcap
data/pcap/<session_id>/<logical_agent_id>.manifest.json
data/pcap/<session_id>/experiment.manifest.json
```

The manifest maps the logical Agent to its container ID, container IP, backend,
trace ID, capture filter, timestamps, and final file size.

The experiment manifest records the explicit/generated simulation seed, scene
file hashes, Agent image IDs, sanitized LLM configuration and its fingerprint,
network profiles, capture lifecycle, and stop reason. Each completed PCAP is
SHA-256 hashed. A quality audit fails on missing captures, missing runtime
identity, hash mismatch, empty capture, or missing trace-matched application
events.

The scheduler delivers each initial goal once. Later rounds wake only Agents
with pending inbox messages; successfully processed inbox snapshots are
acknowledged by message ID, while concurrently arriving messages remain queued.
This prevents artificial repeated LLM traffic from replaying the same goal or
the same inbox on every round.

Direct Agent messages retain source, target, channel, and trace metadata. Both
the sender's MCP tool execution and the receiver's message receipt are written
as application-layer evidence under the same trace.

`PCAP_MAX_BYTES` defaults to 1 GiB per Agent. If tcpdump exits or this limit is
reached, capture health fails and the simulation stops with
`stop_reason=capture_incomplete`; incomplete sessions are never reported as
fully captured runs.

## Optional network conditions

An edge can opt into real Linux `tc`/`netem` conditions:

```json
{
  "source": "PLANNER",
  "target": "RF_ENGINEER",
  "bidirectional": true,
  "network": {
    "delay_ms": 20,
    "jitter_ms": 5,
    "loss_pct": 0.5,
    "rate_mbit": 100
  }
}
```

Delay and loss apply to outbound packets. `bidirectional: true` applies the same
profile in both directions; therefore the approximate RTT contains both one-way
delays. A requested profile that cannot be installed fails the simulation rather
than silently producing traffic under different conditions.

## Analysis API

- `GET /api/packets/?session_id=...&agent_id=...`: newest structured packets.
- `GET /api/packets/stats?session_id=...`: exact PCAP record and byte counts.
- `GET /api/packets/analysis?session_id=...`: bounded summary by protocol,
  direction, traffic class, and endpoint.
- `GET /api/packets/experiment?session_id=...`: immutable experiment inputs,
  seed, scene hashes, runtime identities, and capture lifecycle.
- `GET /api/packets/quality?session_id=...`: capture coverage, identity,
  application-event coverage, and optional SHA-256 verification.
- `GET /api/packets/bundle?session_id=...`: offline analysis ZIP containing
  original PCAPs, manifests, application/network/global JSONL, quality report,
  bounded structured packet JSONL, analysis summary, and `SHA256SUMS.json`.
- `GET /api/packets/download?session_id=...&agent_id=...`: original PCAP.
- `GET /api/packets/correlate?session_id=...&trace_id=...`: explicitly
  labelled temporal-window correlation between application events and packets.

Decoded PCAP records use UTC epoch timestamps. Correlation is an inference and
is reported as such; it is not presented as protocol-level causal proof.

Aggregate counts use `per_agent_observations`: the same Agent-to-Agent packet is
visible in both endpoint PCAPs and is deliberately not presented as a unique
network-wide packet count.

## End-to-end acceptance

With Docker services running, execute:

```bash
python scripts/verify_agent_traffic.py --scene ap_deployment --seed 1234
```

The command exits non-zero unless the simulation completes and the session
passes Agent coverage, runtime identity, non-empty capture, application-event,
and SHA-256 gates. Its output includes the offline bundle URL.
