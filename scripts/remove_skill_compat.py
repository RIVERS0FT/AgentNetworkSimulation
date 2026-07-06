#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace(text: str, old: str, new: str, label: str, count: int = 1) -> str:
    if old not in text:
        raise RuntimeError(f"missing {label}")
    return text.replace(old, new, count)


def sub(text: str, pattern: str, repl: str, label: str, flags: int = 0) -> str:
    updated, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n != 1:
        raise RuntimeError(f"missing {label}")
    return updated


p = "agent_network/agent_model.py"
s = read(p)
s = replace(s, "- skills / tags / capability_scores", "- skill_refs / capability_scores", "agent model doc")
s = replace(s, '''        skills: List[str] = None,
        tags: List[str] = None,
        capability_scores: Dict[str, float] = None,''', '''        skill_refs: List[str] = None,
        capability_scores: Dict[str, float] = None,''', "agent constructor fields")
s = replace(s, '''        self.skills = skills or []
        self.tags = tags or []
        self.capability_scores = capability_scores or {}''', '''        self.skill_refs = list(skill_refs or [])
        self.capability_scores = capability_scores or {}''', "agent constructor assignments")
s = replace(s, '''            "skills": self.skills,
            "tags": self.tags,
            "capability_scores": self.capability_scores,''', '''            "skill_refs": self.skill_refs,
            "capability_scores": self.capability_scores,''', "agent status skills")
s = replace(s, '''    def find_agent(
        cls,
        role: str = None,
        skill: str = None,
        tag: str = None,
    ) -> List[Agent]:''', '''    def find_agent(
        cls,
        role: str = None,
        skill_ref: str = None,
    ) -> List[Agent]:''', "registry find signature")
s = replace(s, '''            if skill and skill not in agent.skills:
                continue
            if tag and tag not in agent.tags:
                continue''', '''            if skill_ref and skill_ref not in agent.skill_refs:
                continue''', "registry find filters")
write(p, s)

p = "agent_network/api/agents.py"
s = read(p)
s = replace(s, '''async def discover_agents(role: str = None, skill: str = None, tag: str = None):
    """服务发现：按条件查询 Agent"""
    agents = AgentRegistry.find_agent(role=role, skill=skill, tag=tag)''', '''async def discover_agents(role: str = None, skill_ref: str = None):
    """服务发现：按角色或技能引用查询 Agent。"""
    agents = AgentRegistry.find_agent(role=role, skill_ref=skill_ref)''', "agent discovery compatibility params")
s = replace(s, '''        skills=req.get("skills", []),
        tags=req.get("tags", []),
        capability_scores=req.get("capability_scores", {})''', '''        skill_refs=req.get("skill_refs", []),
        capability_scores=req.get("capability_scores", {})''', "manual agent registration fields")
write(p, s)

p = "agent_network/api/simulations.py"
s = read(p)
s = replace(s, 'agent = Agent(agent_id=ad.agent_id, role=ad.role, name=ad.name, skills=ad.skills, tags=ad.tags)', 'agent = Agent(agent_id=ad.agent_id, role=ad.role, name=ad.name, skill_refs=ad.skill_refs)', "scene runtime agent construction")
s = replace(s, 'ca = runtime.assign_agent(agent_id=ad.agent_id, role=ad.role, name=ad.name, extra_meta=ad.extra_meta if ad.extra_meta else None)', 'ca = runtime.assign_agent(agent_id=ad.agent_id, role=ad.role, name=ad.name, skill_refs=ad.skill_refs, extra_meta=ad.extra_meta if ad.extra_meta else None)', "container assignment skill refs")
s = replace(s, '''        raw_skills = instance.get("skill_refs") or instance.get("skills") or []
        skills = [s.get("skill_name") or s.get("name") for s in raw_skills] if raw_skills and isinstance(raw_skills[0], dict) else raw_skills
        skills = [s for s in skills if s]''', '''        skill_refs = list(instance.get("skill_refs") or [])
        if not all(isinstance(item, str) and item for item in skill_refs):
            raise ValueError(
                f"Scene '{scene_name}' role '{role_id}' skill_refs must contain non-empty strings."
            )
        skill_refs = list(dict.fromkeys(skill_refs))''', "scene skill compatibility parser")
old_append = '''        agents.append(AgentDef(agent_id=role_id.lower(), role="generic", name=role.get("name", role_id), skills=skills[:4], tags=[paradigm] if paradigm else [], tasks=[core_goal] if core_goal else [], extra_meta={"identity": role.get("identity", ""), "core_goal": core_goal, "initial_assets": role.get("initial_assets", {}), "action_space": ["send_message", "broadcast"] + allowed_tools, "background_rules": bg, "backend": backend, "interaction_paradigm": paradigm, "scene_key": scene_name, "scene_title": title, "allowed_skills": skills, "allowed_tools": allowed_tools, "skill_execution_mode": "backend_native_mcp"}))'''
new_append = '''        identity = role.get("identity", "") or role.get("name", role_id)
        agents.append(
            AgentDef(
                agent_id=role_id.lower(),
                role=identity,
                name=role.get("name", role_id),
                skill_refs=skill_refs,
                tasks=[core_goal] if core_goal else [],
                extra_meta={
                    "core_goal": core_goal,
                    "initial_assets": role.get("initial_assets", {}),
                    "action_space": ["send_message", "broadcast"] + allowed_tools,
                    "background_rules": bg,
                    "backend": backend,
                    "interaction_paradigm": paradigm,
                    "scene_key": scene_name,
                    "scene_title": title,
                    "allowed_tools": allowed_tools,
                    "skill_execution_mode": "backend_native_mcp",
                },
            )
        )'''
s = replace(s, old_append, new_append, "AgentDef scene construction")
write(p, s)

p = "agent_network/container_runtime.py"
s = read(p)
s = replace(s, "from dataclasses import dataclass", "from dataclasses import dataclass, field", "dataclass field import")
s = replace(s, '''    role: str
    container_id: str = ""''', '''    role: str
    skill_refs: List[str] = field(default_factory=list)
    container_id: str = ""''', "container agent skill refs")
s = replace(s, 'def assign_agent(self, agent_id: str, role: str, name: str, extra_meta: Dict = None) -> ContainerAgent:', 'def assign_agent(self, agent_id: str, role: str, name: str, skill_refs: List[str] = None, extra_meta: Dict = None) -> ContainerAgent:', "assign agent signature")
s = replace(s, '''            role=role,
            container_id=container_id,''', '''            role=role,
            skill_refs=list(skill_refs or []),
            container_id=container_id,''', "container agent initialization")
s = replace(s, '''                ctx["role"] = ca.role
                extra_meta = getattr(ca, "_extra_meta", {}) or {}
                for src_key, dst_key in (("core_goal", "core_goal"), ("scene_key", "scene_key"), ("allowed_skills", "allowed_skills")):''', '''                ctx["role"] = ca.role
                ctx["skill_refs"] = list(ca.skill_refs)
                extra_meta = getattr(ca, "_extra_meta", {}) or {}
                for src_key, dst_key in (("core_goal", "core_goal"), ("scene_key", "scene_key")):''', "runtime context skill refs")
write(p, s)

p = "services/agent_server.py"
s = read(p)
s = sub(s, r'\n\ndef _skill_names_from_legacy\(skills: List\[Dict\[str, Any\]\]\) -> List\[str\]:\n(?:    .*\n)+?    return .*\n', "\n", "legacy skill name helper")
s = replace(s, '''    skills: List[Dict[str, Any]] = []
    allowed_skills: List[str] = []
    allowed_tools: List[str] = []''', '''    skill_refs: List[str] = []
    allowed_tools: List[str] = []''', "run request skill fields")
s = replace(s, '''    allowed_skills = req.allowed_skills or _skill_names_from_legacy(req.skills)
    comm.update_directory(req.agent_directory, req.comm_matrix)''', '''    comm.update_directory(req.agent_directory, req.comm_matrix)''', "legacy run skill fallback")
s = replace(s, '''        messages=effective_messages,
        skills=req.skills or [],
        allowed_tools=req.allowed_tools,''', '''        messages=effective_messages,
        skill_refs=req.skill_refs,
        allowed_tools=req.allowed_tools,''', "agent context skill refs")
s = replace(s, '''        scene_key=req.scene_key or os.environ.get("AGENT_SCENE_KEY", "default"),
        allowed_skills=allowed_skills,
        agent_directory=req.agent_directory,''', '''        scene_key=req.scene_key or os.environ.get("AGENT_SCENE_KEY", "default"),
        agent_directory=req.agent_directory,''', "remove allowed skills context")
write(p, s)

p = "agent_network/adapters/base.py"
s = read(p)
s = replace(s, '''    messages: List[Dict[str, Any]]
    skills: List[Dict[str, Any]]
    allowed_tools: List[str]''', '''    messages: List[Dict[str, Any]]
    skill_refs: List[str]
    allowed_tools: List[str]''', "AgentContext skill refs")
s = replace(s, '''    scene_key: str = "default"
    allowed_skills: List[str] = field(default_factory=list)
    agent_directory:''', '''    scene_key: str = "default"
    agent_directory:''', "remove AgentContext allowed skills")
write(p, s)

p = "agent_network/skill_md_loader.py"
s = read(p).replace("allowed_skills", "skill_refs")
write(p, s)

p = "agent_network/adapters/openclaw.py"
s = read(p)
s = sub(s, r'\n\ndef _skill_names\(agent_context: AgentContext\) -> list\[str\]:\n(?:    .*\n)+?    return _unique\(names\)\n', "\n", "openclaw legacy skill names")
s = replace(s, 'registry = load_scene_skill_registry(scene_key=scene_key, scenes_root=scenes_root, allowed_skills=_skill_names(agent_context))', 'registry = load_scene_skill_registry(scene_key=scene_key, scenes_root=scenes_root, skill_refs=agent_context.skill_refs)', "openclaw skill registry args")
s = replace(s, '''    if specs:
        return specs
    return [item for item in (agent_context.skills or []) if isinstance(item, dict)]''', '''    return specs''', "openclaw skill context fallback")
s = replace(s, '''        "allowed_skills": _skill_names(agent_context),
        "skills": _skill_context(agent_context),''', '''        "skill_refs": agent_context.skill_refs,
        "skill_context": _skill_context(agent_context),''', "openclaw payload skill fields")
write(p, s)

p = "agent_network/adapters/claude_code.py"
s = read(p)
s = sub(s, r'\n\ndef _skill_names\(agent_context: AgentContext\) -> list\[str\]:\n(?:    .*\n)+?    return _unique\(names\)\n', "\n", "claude legacy skill names")
s = replace(s, 'registry = load_scene_skill_registry(scene_key=scene_key, scenes_root=scenes_root, allowed_skills=_skill_names(agent_context))', 'registry = load_scene_skill_registry(scene_key=scene_key, scenes_root=scenes_root, skill_refs=agent_context.skill_refs)', "claude skill registry args")
s = replace(s, '''    if specs:
        return specs
    return [item for item in (agent_context.skills or []) if isinstance(item, dict)]''', '''    return specs''', "claude skill context fallback")
s = replace(s, '''        "allowed_skills": _skill_names(agent_context),
        "skills": _skill_context(agent_context),''', '''        "skill_refs": agent_context.skill_refs,
        "skill_context": _skill_context(agent_context),''', "claude payload skill fields")
s = replace(s, 'def _claude_mcp_server(agent_context: AgentContext, skill_names: list[str]) -> dict:', 'def _claude_mcp_server(agent_context: AgentContext) -> dict:', "claude mcp signature")
s = replace(s, '''            "--agent-name", agent_context.agent_name,
            "--allowed-skills", ",".join(skill_names),
            "--allowed-tools",''', '''            "--agent-name", agent_context.agent_name,
            "--allowed-tools",''', "claude mcp skill CLI")
s = replace(s, "        skill_names = _skill_names(agent_context)\n", "", "claude skill names local")
s = replace(s, '"mcp_servers": {"agent_tools": _claude_mcp_server(agent_context, skill_names)},', '"mcp_servers": {"agent_tools": _claude_mcp_server(agent_context)},', "claude mcp call")
write(p, s)

p = "agent_network/adapters/direct_llm.py"
s = read(p)
s = sub(s, r'\n\ndef _skill_names\(agent_context: AgentContext\) -> list\[str\]:\n(?:    .*\n)+?    return _unique\(names\)\n', "\n", "direct llm legacy skill names")
s = replace(s, '''        allowed_skills=_skill_names(agent_context),''', '''        skill_refs=agent_context.skill_refs,''', "direct llm registry args")
s = replace(s, '''    if specs:
        return specs
    return [item for item in (agent_context.skills or []) if isinstance(item, dict)]''', '''    return specs''', "direct llm skill context fallback")
s = replace(s, '''        "allowed_skills": _skill_names(agent_context),
        "skills": _skill_context(agent_context),''', '''        "skill_refs": agent_context.skill_refs,
        "skill_context": _skill_context(agent_context),''', "direct llm payload fields")
write(p, s)

p = "agent_network/mcp_server.py"
s = read(p)
s = replace(s, "from agent_network.skill_md_loader import parse_skill_md\n", "", "MCP skill parser import")
s = replace(s, "_ALLOWED_SKILLS = set()\n", "", "MCP allowed skill global")
s = replace(s, "_SKILLS_CACHE = {}\n", "", "MCP skill cache global")
s = replace(s, "    allowed_skills: list,\n", "", "MCP setup skill arg")
s = replace(s, '''    global _SCENE_KEY, _AGENT_ID, _AGENT_NAME, _ALLOWED_SKILLS, _ALLOWED_TOOLS
    global _SCENES_ROOT, _SKILLS_CACHE, _TOOL_REGISTRY, _AGENT_DIRECTORY, _COMM_MATRIX, _COMM, _TRACE_ID''', '''    global _SCENE_KEY, _AGENT_ID, _AGENT_NAME, _ALLOWED_TOOLS
    global _SCENES_ROOT, _TOOL_REGISTRY, _AGENT_DIRECTORY, _COMM_MATRIX, _COMM, _TRACE_ID''', "MCP setup globals")
s = replace(s, "    _ALLOWED_SKILLS = set(allowed_skills or [])\n", "", "MCP setup allowed skills")
s = replace(s, "    _SKILLS_CACHE = {}\n", "", "MCP setup skill cache")
s = sub(s, r'\n    skill_dir = _SCENES_ROOT / _SCENE_KEY / "skills"\n    if skill_dir\.exists\(\) and skill_dir\.is_dir\(\):\n(?:        .*\n)+?            _SKILLS_CACHE\[s_name\] = parsed\n', "\n", "MCP skill loading block")
s = replace(s, '    parser.add_argument("--allowed-skills", default="")\n', "", "MCP skill CLI arg")
s = replace(s, '        allowed_skills=args.allowed_skills.split(",") if args.allowed_skills else [],\n', "", "MCP setup skill CLI value")
write(p, s)

p = "tests/test_scene_building_boundary.py"
s = read(p)
s = replace(s, "def test_scene_building_uses_core_goal_as_task_and_skills_as_context", "def test_scene_building_uses_identity_role_and_skill_refs", "scene test name")
s = replace(s, '''    assert agent.tasks == ["Coordinate the team"]
    assert agent.skills == ["planning", "reporting"]
    assert agent.extra_meta["allowed_tools"] == ["write_plan"]
    assert agent.extra_meta["allowed_skills"] == ["planning", "reporting"]
    assert "skills_list" not in agent.extra_meta''', '''    assert agent.role == "Leader"
    assert agent.tasks == ["Coordinate the team"]
    assert agent.skill_refs == ["planning", "reporting"]
    assert agent.extra_meta["allowed_tools"] == ["write_plan"]
    assert "identity" not in agent.extra_meta
    assert "allowed_skills" not in agent.extra_meta
    assert "skills_list" not in agent.extra_meta''', "scene test assertions")
write(p, s)

p = "tests/test_container_runtime_boundary.py"
s = read(p)
s = replace(s, '''        role="planner",
        url="http://agent-a:8000",''', '''        role="planner",
        skill_refs=["planning"],
        url="http://agent-a:8000",''', "container test skill refs")
s = replace(s, '        "allowed_skills": ["planning"],\n', "", "container test old metadata")
s = replace(s, '''    assert "skills" not in posted["json"]
    assert posted["json"]["allowed_skills"] == ["planning"]''', '''    assert "skills" not in posted["json"]
    assert "allowed_skills" not in posted["json"]
    assert posted["json"]["skill_refs"] == ["planning"]''', "container posted skill refs")
write(p, s)

p = "tests/test_mcp_server_boundary.py"
s = read(p)
s = sub(s, r'\n\ndef test_setup_runtime_keeps_skill_metadata_as_context_only\(tmp_path\):\n(?:    .*\n)+?    assert mcp_server\._SKILLS_CACHE\["planning"\]\["sop_content"\] == "Planning SOP\."\n', '''\n\ndef test_mcp_server_does_not_cache_or_parse_skill_content(tmp_path):
    import agent_network.mcp_server as mcp_server

    mcp_server.setup_runtime(
        scene_key="demo",
        agent_id="agent_a",
        agent_name="Agent A",
        allowed_tools=[],
        scenes_root=str(tmp_path),
    )

    assert not hasattr(mcp_server, "_SKILLS_CACHE")
    assert not hasattr(mcp_server, "_ALLOWED_SKILLS")
''', "MCP skill cache test")
write(p, s)

p = "tests/test_skill_md_loader_context_only.py"
s = read(p).replace("LocalSkillRegistry(allowed_skills=", "LocalSkillRegistry(skill_refs=")
write(p, s)

p = "tests/test_adapter_context_boundary.py"
s = read(p)
s = sub(s, r'''        skills=\[\n            \{\n(?:                .*\n)+?            \}\n        \],''', '''        skill_refs=["planning"],''', "adapter context skill objects")
s = replace(s, '''    assert payload["skills"][0]["name"] == "planning"
    assert payload["skills"][0]["sop_content"] == "Plan step by step"''', '''    assert payload["skill_refs"] == ["planning"]
    assert payload["skill_context"] == []''', "claude payload skill assertions")
s = replace(s, '    server = claude_code._claude_mcp_server(_context(), ["planning"])', '    server = claude_code._claude_mcp_server(_context())', "claude MCP test call")
s = replace(s, '    assert payload["skills"][0]["tools"] == ["write_plan"]', '    assert payload["skill_refs"] == ["planning"]\n    assert payload["skill_context"] == []', "openclaw payload skill assertions")
write(p, s)

p = "tests/test_agent_server_boundary.py"
s = read(p)
s += '''\n\n
def test_agent_server_exposes_only_skill_refs_contract():
    text = _text()

    assert "skill_refs: List[str]" in text
    assert "allowed_skills" not in text
    assert "_skill_names_from_legacy" not in text
    assert "skills: List[Dict" not in text
'''
write(p, s)

for p in ("docs/AgentRuntimeBoundary.md", "docs/设计文档.md"):
    s = read(p).replace("allowed_skills", "skill_refs")
    write(p, s)

runtime_files = [
    "agent_network/scene_def.py",
    "agent_network/agent_model.py",
    "agent_network/api/agents.py",
    "agent_network/api/simulations.py",
    "agent_network/container_runtime.py",
    "services/agent_server.py",
    "agent_network/adapters/base.py",
    "agent_network/adapters/openclaw.py",
    "agent_network/adapters/claude_code.py",
    "agent_network/adapters/direct_llm.py",
    "agent_network/mcp_server.py",
]
for path in runtime_files:
    text = read(path)
    for forbidden in ("allowed_skills", "_SKILLS_CACHE", "_ALLOWED_SKILLS", "_skill_names_from_legacy"):
        if forbidden in text:
            raise RuntimeError(f"{forbidden} remains in {path}")

print("skill compatibility fields removed")
