"""Skill Registry stub"""
class SkillRegistry:
    _skills = {}
    @classmethod
    def list_skills(cls): return list(cls._skills.keys())
    @classmethod
    def execute(cls, skill_name, **kwargs): return {"error": "skills removed"}
    @classmethod
    def get_stats(cls): return {"total_calls": 0}
    @classmethod
    def reset(cls): pass
