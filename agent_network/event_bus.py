"""EventBus + PacketRecorder stubs"""
from typing import Dict, List, Any

class PacketRecorder:
    _records: List[Any] = []
    @classmethod
    def record(cls, direction, message, **kw): pass
    @classmethod
    def get_records(cls, agent_id=None): return []
    @classmethod
    def get_stats(cls): return {"total_packets": 0}
    @classmethod
    def reset(cls): cls._records.clear()

class EventBus:
    def __init__(self, name="default"): self.name = name
    def publish(self, msg): return 0
    def reset(self): pass
