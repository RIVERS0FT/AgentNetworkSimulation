"""Tool Registry stub"""
class ToolRegistry:
    _tools = {}
    @classmethod
    def list_tools(cls): return list(cls._tools.keys())
    @classmethod
    def execute(cls, tool_name, **kwargs): return {"error": "tools removed"}
    @classmethod
    def get_stats(cls): return {"total_calls": 0}
    @classmethod
    def reset(cls): pass
