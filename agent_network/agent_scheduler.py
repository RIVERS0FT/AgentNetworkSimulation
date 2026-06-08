"""Scheduler stub"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any

class TaskPriority(Enum): CRITICAL=0; HIGH=1; NORMAL=2; LOW=3; BACKGROUND=4
class TaskStatus(Enum): PENDING="pending"; RUNNING="running"; COMPLETED="completed"; FAILED="failed"

@dataclass(order=True)
class ScheduledTask:
    priority: int = 2
    action: str = ""; target_agent_id: str = ""; params: Dict = field(default_factory=dict)
    source_script: str = ""
