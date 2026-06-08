"""Engine stub"""
from typing import Dict, Any

class SimulationEngine:
    def __init__(self, name=""): self.name = name
    def register_agent(self, agent): pass
    def load_script(self, script): pass
    def run(self): return {"agents": [], "agent_stats": {"total_agents": 0}}
