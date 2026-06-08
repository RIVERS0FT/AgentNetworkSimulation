"""SimulationLogger stub"""
from enum import Enum
from typing import Dict, Any, List

class LogLevel(Enum):
    TRACE=0; DEBUG=1; INFO=2; WARN=3; ERROR=4; FATAL=5; AUDIT=6

class LogEntry:
    def to_dict(self): return {}

class SimulationLogger:
    def __init__(self, name=""): self.name = name
    def system(self, msg, level=None, **kw): pass
    def get_entries(self): return []
    def get_index_stats(self): return {"total": 0}
    def query(self, **kw): return []
