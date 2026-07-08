"""
AI Agent 仿真运行平台 - Agent Network Simulation Platform
========================================================
企业级 AI Agent 仿真、推演与编排平台。

Modules:
- core: 核心抽象 (Agent, Tool, Skill, Message)
- registry: Agent 注册与发现
- simulation: 仿真引擎与事件总线
- log_manager: 日志记录与文件管理
"""

__version__ = "0.1.0"

# Install the packet-oriented network.jsonl contract before callers import
# agent_network.log_manager.  Application and system log schemas are unchanged.
from .network_log_v4 import apply as _apply_network_log_v4

_apply_network_log_v4()
del _apply_network_log_v4
