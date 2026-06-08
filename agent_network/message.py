"""Message stub (real impl in agent.py)"""
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class PacketRecord:
    direction: str; source_agent: str; target_agent: str
    message_type: str; payload_hash: str = ""; token_usage: int = 0; latency: float = 0
