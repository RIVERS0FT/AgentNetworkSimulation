#!/usr/bin/env python3
"""Deprecated message bus service.

The Agent message data plane has been removed. Agents now communicate directly
through Agent-to-Agent HTTP using DirectBus. This service is kept only as a
minimal compatibility stub for deployments that still start it accidentally.
"""

import os
import uvicorn
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Deprecated AgentNetwork Message Bus")


@app.get("/health")
async def health():
    return {"status": "deprecated", "data_plane": "removed", "network_mode": "direct"}


@app.get("/agents")
async def list_agents():
    return {"agents": {}, "aliases": {}, "count": 0, "deprecated": True}


@app.post("/register")
async def register_agent(agent_id: str, url: str, name: str = ""):
    return {"status": "ignored", "reason": "DirectBus uses srv-provided agent_directory", "agent_id": agent_id, "url": url, "name": name}


@app.post("/relay")
async def relay_removed():
    raise HTTPException(status_code=410, detail="message bus relay data plane removed; use direct Agent-to-Agent communication")


@app.get("/packets")
async def packets_removed():
    raise HTTPException(status_code=410, detail="packet API moved to srv /api/packets and reads tcpdump pcap")


@app.get("/packets/stream")
async def packet_stream_removed():
    raise HTTPException(status_code=410, detail="packet stream moved to srv /api/packets/stream")


@app.get("/packets/stats")
async def packet_stats_removed():
    raise HTTPException(status_code=410, detail="packet stats moved to srv /api/packets/stats")


if __name__ == "__main__":
    port = int(os.environ.get("BUS_PORT", os.environ.get("MESSAGE_BUS_PORT", 9000)))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
