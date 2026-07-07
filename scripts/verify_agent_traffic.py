#!/usr/bin/env python3
"""Run one real simulation and fail unless its traffic dataset passes quality gates."""

import argparse
import json
import sys

import requests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--scene", required=True)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    base = args.server.rstrip("/")

    setup = requests.post(
        f"{base}/api/simulations/setup",
        json={"scene": args.scene, "seed": args.seed},
        timeout=30,
    )
    setup.raise_for_status()
    launch = requests.post(f"{base}/api/simulations/launch", timeout=args.timeout)
    launch.raise_for_status()
    result = launch.json()
    session_id = result.get("session_id", "")
    if not session_id:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("ERROR: simulation did not return a session_id", file=sys.stderr)
        return 2

    quality_response = requests.get(
        f"{base}/api/packets/quality",
        params={"session_id": session_id, "verify_hashes": "true"},
        timeout=300,
    )
    quality_response.raise_for_status()
    quality = quality_response.json()
    summary = {
        "session_id": session_id,
        "seed": result.get("seed"),
        "simulation_status": result.get("status"),
        "experiment_status": result.get("experiment_status"),
        "stop_reason": result.get("stop_reason"),
        "packet_stats": result.get("packet_stats"),
        "quality": quality,
        "bundle_url": f"{base}/api/packets/bundle?session_id={session_id}",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if result.get("status") != "completed" or not quality.get("passed"):
        print("ERROR: real Agent traffic verification failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
