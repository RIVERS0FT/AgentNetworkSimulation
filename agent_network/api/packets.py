from typing import Optional
from fastapi import APIRouter, Query

from agent_network.real_packet_store import packet_stats, query_packets, wireshark_lines

router = APIRouter()


@router.get("/")
async def packets(
    agent_id: Optional[str] = Query(None),
    session_id: str = Query(default=""),
    limit: int = Query(default=100, le=1000),
):
    records = query_packets(session_id=session_id, agent_id=agent_id, limit=limit)
    return {
        "source": "real",
        "capture_source": "tcpdump_pcap",
        "total": len(records),
        "packets": records,
        "stats": packet_stats(session_id=session_id),
    }


@router.get("/stats")
async def stats(session_id: str = Query(default="")):
    return packet_stats(session_id=session_id)


@router.get("/stream")
async def stream(
    agent_id: Optional[str] = Query(None),
    session_id: str = Query(default=""),
    limit: int = Query(default=100, le=1000),
):
    return {"lines": wireshark_lines(session_id=session_id, agent_id=agent_id, limit=limit)}
