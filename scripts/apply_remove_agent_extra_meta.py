#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, text: str) -> None:
    path = ROOT / relative
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"cannot locate {label}")
    return text.replace(old, new, 1)


def patch_scene_def() -> None:
    path = "agent_network/scene_def.py"
    text = read(path)
    text = replace_once(
        text,
        '''@dataclass
class AgentDef:
    """场景配置中的单个 Agent 定义。"""
    agent_id: str
    role: str  # 直接保存角色 identity 内容
    name: str
    skill_refs: List[str] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)
    extra_meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SceneDefinition:
    """完整场景定义。"""
    scene_name: str = ""
    description: str = ""
    agents: List[AgentDef] = field(default_factory=list)
    topology: List[Dict[str, Any]] = field(default_factory=list)
''',
        '''@dataclass
class AgentDef:
    """场景配置中的单个 Agent 定义。"""
    agent_id: str
    role: str  # 直接保存角色 identity 内容
    name: str
    core_goal: str = ""
    backend: str = "openclaw"
    skill_refs: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)


@dataclass
class SceneDefinition:
    """完整场景定义。"""
    scene_key: str = ""
    title: str = ""
    description: str = ""
    agents: List[AgentDef] = field(default_factory=list)
    topology: List[Dict[str, Any]] = field(default_factory=list)
''',
        "AgentDef and SceneDefinition models",
    )
    write(path, text)


def patch_agent_model() -> None:
    path = "agent_network/agent_model.py"
    text = read(path)
    text = text.replace("- position / extra_meta", "- position / explicit runtime metadata")
    text = replace_once(
        text,
        '''        name: str = "",
        skill_refs: List[str] = None,
        capability_scores: Dict[str, float] = None,
''',
        '''        name: str = "",
        core_goal: str = "",
        backend: str = "openclaw",
        skill_refs: List[str] = None,
        allowed_tools: List[str] = None,
        capability_scores: Dict[str, float] = None,
''',
        "Agent constructor signature",
    )
    text = replace_once(
        text,
        '''        self.name = name or self.agent_id
        self.skill_refs = list(skill_refs or [])
        self.capability_scores = capability_scores or {}
''',
        '''        self.name = name or self.agent_id
        self.core_goal = core_goal
        self.backend = backend
        self.skill_refs = list(skill_refs or [])
        self.allowed_tools = list(allowed_tools or [])
        self.capability_scores = capability_scores or {}
''',
        "Agent explicit runtime fields",
    )
    text = replace_once(
        text,
        '''        self.pending_task_descs: List[str] = []
        self.extra_meta: Dict[str, Any] = {}
        self._created_at = datetime.now().isoformat(timespec="seconds")
''',
        '''        self.pending_task_descs: List[str] = []
        self._created_at = datetime.now().isoformat(timespec="seconds")
''',
        "Agent extra_meta removal",
    )
    text = replace_once(
        text,
        '''            "role": self.role,
            "url": getattr(self, "container_url", ""),
''',
        '''            "role": self.role,
            "core_goal": self.core_goal,
            "backend": self.backend,
            "allowed_tools": self.allowed_tools,
            "url": getattr(self, "container_url", ""),
''',
        "Agent status explicit fields",
    )
    text = replace_once(text, '            "extra_meta": self.extra_meta,\n', "", "Agent status extra_meta")
    write(path, text)


def patch_simulations() -> None:
    path = "agent_network/api/simulations.py"
    text = read(path)
    text = replace_once(
        text,
        '''    for ad in scene_def.agents:
        agent = Agent(agent_id=ad.agent_id, role=ad.role, name=ad.name, skill_refs=ad.skill_refs)
        agent.set_comm(direct_bus)
        agent.x, agent.y = pos.get(ad.agent_id, (100, 100))
        agent.pending_task_descs = ad.tasks
        agent.extra_meta = ad.extra_meta
        AgentRegistry.register(agent)
        agent.start()
    _pending_scene_def = scene_def
    return {"agents": [a.get_status() for a in AgentRegistry.list_all()], "agent_stats": AgentRegistry.get_stats(), "topology": scene_def.topology, "scene_name": scene_def.scene_name, "network_mode": "direct", "seed": _pending_seed}
''',
        '''    for ad in scene_def.agents:
        agent = Agent(
            agent_id=ad.agent_id,
            role=ad.role,
            name=ad.name,
            core_goal=ad.core_goal,
            backend=ad.backend,
            skill_refs=ad.skill_refs,
            allowed_tools=ad.allowed_tools,
        )
        agent.set_comm(direct_bus)
        agent.x, agent.y = pos.get(ad.agent_id, (100, 100))
        agent.pending_task_descs = ad.tasks
        AgentRegistry.register(agent)
        agent.start()
    _pending_scene_def = scene_def
    return {
        "agents": [a.get_status() for a in AgentRegistry.list_all()],
        "agent_stats": AgentRegistry.get_stats(),
        "topology": scene_def.topology,
        "scene_key": scene_def.scene_key,
        "scene_title": scene_def.title,
        "network_mode": "direct",
        "seed": _pending_seed,
    }
''',
        "control-plane Agent setup",
    )
    text = replace_once(
        text,
        '''    for ad in scene_def.agents:
        ca = runtime.assign_agent(agent_id=ad.agent_id, role=ad.role, name=ad.name, skill_refs=ad.skill_refs, extra_meta=ad.extra_meta if ad.extra_meta else None)
        created_cas.append((ca, ad.tasks))
        if ca.status == "error":
            assign_errors.append({"agent_id": ca.agent_id, "error": getattr(ca, "_assign_error", "unknown")})
''',
        '''    for ad in scene_def.agents:
        ca = runtime.assign_agent(
            agent_id=ad.agent_id,
            role=ad.role,
            name=ad.name,
            core_goal=ad.core_goal,
            backend=ad.backend,
            skill_refs=ad.skill_refs,
            allowed_tools=ad.allowed_tools,
            scene_key=scene_def.scene_key,
        )
        created_cas.append((ca, ad.tasks))
        if ca.status == "error":
            assign_errors.append({"agent_id": ca.agent_id, "error": ca.assign_error or "unknown"})
''',
        "container assignment",
    )
    text = text.replace("logger.start_session(scene_def.scene_name)", "logger.start_session(scene_def.scene_key)")
    text = text.replace('"backend": (getattr(ca, "_extra_meta", {}) or {}).get("backend", ""),', '"backend": ca.backend,')
    text = text.replace("scene_name=scene_def.scene_name,", "scene_name=scene_def.scene_key,")
    text = text.replace('"scene": scene_def.scene_name,', '"scene": scene_def.scene_key,')
    text = replace_once(
        text,
        'return {"status": "error" if run_error else "completed", "error": run_error, "simulation_name": scene_def.scene_name,',
        'return {"status": "error" if run_error else "completed", "error": run_error, "simulation_name": scene_def.title, "scene_key": scene_def.scene_key,',
        "simulation result scene identity",
    )
    text = replace_once(
        text,
        '''def _normalize_backend(scene_name: str, role_id: str, backend: str) -> str:
    backend = (backend or "openclaw").strip()
    if backend == "claudecode":
        return "claude-code"
    if backend == "brain":
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses removed backend 'brain'.")
    if backend not in {"openclaw", "claude-code"}:
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses unsupported backend '{backend}'.")
    return backend
''',
        '''def _normalize_backend(scene_name: str, role_id: str, backend: str) -> str:
    backend = (backend or "openclaw").strip()
    if backend == "brain":
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses removed backend 'brain'.")
    if backend == "claudecode":
        raise ValueError(
            f"Scene '{scene_name}' role '{role_id}' uses removed backend alias 'claudecode'; "
            "use 'claude-code'."
        )
    if backend not in {"openclaw", "claude-code"}:
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses unsupported backend '{backend}'.")
    return backend
''',
        "strict scene backend normalization",
    )
    text = replace_once(text, '        paradigm = role.get("primary_interaction_paradigm", "")\n', "", "unused interaction paradigm")
    text = replace_once(
        text,
        '''            AgentDef(
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
''',
        '''            AgentDef(
                agent_id=role_id.lower(),
                role=identity,
                name=role.get("name", role_id),
                core_goal=core_goal,
                backend=backend,
                skill_refs=skill_refs,
                allowed_tools=list(allowed_tools),
                tasks=[],
            )
''',
        "strict AgentDef construction",
    )
    text = replace_once(
        text,
        "    return SceneDefinition(scene_name=title, description=bg, agents=agents, topology=topology_edges)\n",
        '''    return SceneDefinition(
        scene_key=scene_name,
        title=title,
        description=bg,
        agents=agents,
        topology=topology_edges,
    )
''',
        "SceneDefinition construction",
    )
    write(path, text)


def patch_container_runtime() -> None:
    path = "agent_network/container_runtime.py"
    text = read(path)
    text = replace_once(
        text,
        'from dataclasses import dataclass, field\n\n\n@dataclass\n',
        'from dataclasses import dataclass, field\n\n\nSYSTEM_TOOLS = ("send_message", "broadcast")\n\n\n@dataclass\n',
        "system tools constant",
    )
    text = replace_once(
        text,
        '''class ContainerAgent:
    agent_id: str
    name: str
    role: str
    skill_refs: List[str] = field(default_factory=list)
    container_id: str = ""
''',
        '''class ContainerAgent:
    agent_id: str
    name: str
    role: str
    core_goal: str = ""
    backend: str = "openclaw"
    skill_refs: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    scene_key: str = ""
    container_id: str = ""
''',
        "ContainerAgent explicit fields",
    )
    text = replace_once(
        text,
        '    status: str = "idle"\n    url: str = ""\n',
        '    status: str = "idle"\n    url: str = ""\n    assign_error: str = ""\n',
        "ContainerAgent assignment error",
    )
    text = replace_once(
        text,
        '''        backend = (backend or self.DEFAULT_BACKEND).strip()
        if backend == "claudecode":
            return "claude-code"
        if backend == "brain":
''',
        '''        backend = (backend or self.DEFAULT_BACKEND).strip()
        if backend == "brain":
''',
        "runtime claudecode alias",
    )
    text = replace_once(
        text,
        '''    def assign_agent(self, agent_id: str, role: str, name: str, skill_refs: List[str] = None, extra_meta: Dict = None) -> ContainerAgent:
        extra_meta = extra_meta or {}
        try:
            backend = self._normalize_backend(extra_meta.get("backend", self.DEFAULT_BACKEND))
''',
        '''    def assign_agent(
        self,
        agent_id: str,
        role: str,
        name: str,
        core_goal: str = "",
        backend: str = "openclaw",
        skill_refs: List[str] = None,
        allowed_tools: List[str] = None,
        scene_key: str = "",
    ) -> ContainerAgent:
        try:
            backend = self._normalize_backend(backend)
''',
        "assign_agent signature",
    )
    text = replace_once(
        text,
        '''            role=role,
            skill_refs=list(skill_refs or []),
            container_id=container_id,
''',
        '''            role=role,
            core_goal=core_goal,
            backend=backend,
            skill_refs=list(skill_refs or []),
            allowed_tools=list(allowed_tools or []),
            scene_key=scene_key,
            container_id=container_id,
''',
        "ContainerAgent construction fields",
    )
    text = replace_once(
        text,
        '''            status=status,
        )
        ca._extra_meta = extra_meta
        ca._assign_error = assign_error
''',
        '''            status=status,
            assign_error=assign_error or "",
        )
''',
        "dynamic container metadata removal",
    )
    text = replace_once(
        text,
        '''                ctx["role"] = ca.role
                ctx["skill_refs"] = list(ca.skill_refs)
                extra_meta = getattr(ca, "_extra_meta", {}) or {}
                for src_key, dst_key in (("core_goal", "core_goal"), ("scene_key", "scene_key")):
                    if extra_meta.get(src_key):
                        ctx[dst_key] = extra_meta[src_key]
                if extra_meta.get("action_space"):
                    ctx["allowed_tools"] = extra_meta["action_space"]
                if extra_meta.get("allowed_tools"):
                    ctx["allowed_tools"] = list(dict.fromkeys((ctx.get("allowed_tools") or []) + extra_meta["allowed_tools"]))
''',
        '''                ctx["role"] = ca.role
                ctx["core_goal"] = ca.core_goal
                ctx["skill_refs"] = list(ca.skill_refs)
                ctx["allowed_tools"] = list(
                    dict.fromkeys([*SYSTEM_TOOLS, *ca.allowed_tools])
                )
                ctx["scene_key"] = ca.scene_key
''',
        "explicit run context",
    )
    write(path, text)


def patch_agent_server() -> None:
    path = "services/agent_server.py"
    text = read(path)
    for line in (
        'AGENT_ACTION_SPACE = json.loads(os.environ.get("AGENT_ACTION_SPACE", "[]"))\n',
        'AGENT_INITIAL_ASSETS = json.loads(os.environ.get("AGENT_INITIAL_ASSETS", "{}"))\n',
        'AGENT_INTERACTION_PARADIGM = os.environ.get("AGENT_INTERACTION_PARADIGM", "")\n',
    ):
        if line not in text:
            raise RuntimeError(f"cannot locate removed environment field: {line.strip()}")
        text = text.replace(line, "", 1)
    text = replace_once(
        text,
        '''BACKEND = os.environ.get("AGENT_BACKEND", "openclaw")
if BACKEND == "claudecode":
    BACKEND = "claude-code"
''',
        '''BACKEND = os.environ.get("AGENT_BACKEND", "openclaw")
''',
        "agent server claudecode alias",
    )
    write(path, text)


def patch_scene_test() -> None:
    path = "tests/test_scene_building_boundary.py"
    text = read(path)
    text = replace_once(
        text,
        '''    assert agent.agent_id == "ceo"
    assert agent.role == "Leader"
    assert agent.tasks == ["Coordinate the team"]
    assert agent.skill_refs == ["planning", "reporting"]
    assert agent.extra_meta["allowed_tools"] == ["write_plan"]
    assert "identity" not in agent.extra_meta
    assert "allowed_skills" not in agent.extra_meta
    assert "skills_list" not in agent.extra_meta
    assert agent.extra_meta["action_space"] == ["send_message", "broadcast", "write_plan"]
    assert agent.extra_meta["skill_execution_mode"] == "backend_native_mcp"
''',
        '''    assert scene_def.scene_key == "demo_scene"
    assert scene_def.title == "Demo Scene"
    assert scene_def.description == "Global rules"
    assert agent.agent_id == "ceo"
    assert agent.role == "Leader"
    assert agent.core_goal == "Coordinate the team"
    assert agent.backend == "openclaw"
    assert agent.tasks == []
    assert agent.skill_refs == ["planning", "reporting"]
    assert agent.allowed_tools == ["write_plan"]
    assert not hasattr(agent, "extra_meta")
''',
        "scene model assertions",
    )
    text = replace_once(
        text,
        '''def test_scene_building_normalizes_claudecode_backend(tmp_path, monkeypatch):
    _write_scene(tmp_path, backend="claudecode")
    monkeypatch.setattr(simulations, "_SCENES_DIR", tmp_path)

    scene_def = simulations._build_scene_from_folder("demo_scene")

    assert scene_def.agents[0].extra_meta["backend"] == "claude-code"
''',
        '''def test_scene_building_rejects_removed_claudecode_backend(tmp_path, monkeypatch):
    _write_scene(tmp_path, backend="claudecode")
    monkeypatch.setattr(simulations, "_SCENES_DIR", tmp_path)

    with pytest.raises(ValueError) as exc:
        simulations._build_scene_from_folder("demo_scene")

    assert "removed backend alias 'claudecode'" in str(exc.value)
''',
        "scene claudecode test",
    )
    write(path, text)


def patch_container_test() -> None:
    path = "tests/test_container_runtime_boundary.py"
    text = read(path)
    text = replace_once(
        text,
        '''def test_container_runtime_normalizes_claudecode_backend(monkeypatch):
    runtime = _runtime(monkeypatch)

    assert runtime._normalize_backend("claudecode") == "claude-code"
''',
        '''def test_container_runtime_rejects_claudecode_backend(monkeypatch):
    runtime = _runtime(monkeypatch)

    with pytest.raises(RuntimeError) as exc:
        runtime._normalize_backend("claudecode")

    assert "Unsupported backend" in str(exc.value)
''',
        "runtime claudecode test",
    )
    text = replace_once(
        text,
        '''    ca = ContainerAgent(
        agent_id="agent_a",
        name="Agent A",
        role="planner",
        url="http://agent-a:8000",
        status="idle",
    )
    ca._extra_meta = {
        "core_goal": "Coordinate",
        "action_space": ["send_message"],
        "scene_key": "demo_scene",
        "allowed_tools": ["write_plan"],
    }
''',
        '''    ca = ContainerAgent(
        agent_id="agent_a",
        name="Agent A",
        role="planner",
        core_goal="Coordinate",
        backend="openclaw",
        skill_refs=["planning"],
        allowed_tools=["write_plan"],
        scene_key="demo_scene",
        url="http://agent-a:8000",
        status="idle",
    )
''',
        "explicit ContainerAgent test fixture",
    )
    text = text.replace('    assert posted["json"]["allowed_tools"] == ["send_message", "write_plan"]\n', '    assert posted["json"]["allowed_tools"] == ["send_message", "broadcast", "write_plan"]\n    assert posted["json"]["core_goal"] == "Coordinate"\n    assert not hasattr(ca, "_extra_meta")\n')
    write(path, text)


def patch_agent_model_test() -> None:
    path = "tests/test_agent_model_control_plane_only.py"
    text = read(path)
    text = replace_once(
        text,
        '''        role="planner",
        name="Agent A",
        skill_refs=["planning"],
''',
        '''        role="planner",
        name="Agent A",
        core_goal="Plan work",
        backend="openclaw",
        skill_refs=["planning"],
        allowed_tools=["write_plan"],
''',
        "Agent model test fixture",
    )
    text = replace_once(
        text,
        '''    assert status["role"] == "planner"
    assert status["skill_refs"] == ["planning"]
''',
        '''    assert status["role"] == "planner"
    assert status["core_goal"] == "Plan work"
    assert status["backend"] == "openclaw"
    assert status["skill_refs"] == ["planning"]
    assert status["allowed_tools"] == ["write_plan"]
    assert "extra_meta" not in status
    assert not hasattr(agent, "extra_meta")
''',
        "Agent model status assertions",
    )
    write(path, text)


def migrate_scene_backend_values() -> None:
    for path in sorted((ROOT / "scenes").rglob("*.json")):
        text = path.read_text(encoding="utf-8")
        updated = re.sub(
            r'("model_backbone"\s*:\s*)"claudecode"',
            r'\1"claude-code"',
            text,
        )
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")

    for relative in ("scenes/scenario.py", "scenes/README.md", "scenes/PANEL_API.md"):
        path = ROOT / relative
        if path.exists():
            text = path.read_text(encoding="utf-8")
            text = text.replace("claudecode", "claude-code")
            path.write_text(text, encoding="utf-8", newline="\n")


def patch_docs() -> None:
    replacements = {
        "docs/AgentRuntimeBoundary.md": [
            ("extra_meta", "explicit AgentDef fields"),
            ("action_space", "allowed_tools"),
            ("skill_execution_mode", "backend-native MCP execution"),
        ],
        "docs/设计文档.md": [
            ("extra_meta", "显式 Agent 运行字段"),
            ("action_space", "allowed_tools"),
            ("skill_execution_mode", "backend-native MCP 执行模式"),
        ],
    }
    for relative, items in replacements.items():
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for old, new in items:
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8", newline="\n")


def validate() -> None:
    runtime_files = [
        ROOT / "agent_network" / "scene_def.py",
        ROOT / "agent_network" / "agent_model.py",
        ROOT / "agent_network" / "container_runtime.py",
        ROOT / "agent_network" / "api" / "simulations.py",
        ROOT / "services" / "agent_server.py",
    ]
    forbidden = ("extra_meta", "_extra_meta", "skill_execution_mode", '"action_space"')
    for path in runtime_files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                raise RuntimeError(f"legacy token {token!r} remains in {path.relative_to(ROOT)}")

    scene_def = read("agent_network/scene_def.py")
    for token in ("core_goal: str", "backend: str", "allowed_tools: List[str]", "scene_key: str", "title: str"):
        if token not in scene_def:
            raise RuntimeError(f"missing explicit model field {token}")

    container_runtime = read("agent_network/container_runtime.py")
    for token in ("SYSTEM_TOOLS", "ca.core_goal", "ca.allowed_tools", "ca.scene_key"):
        if token not in container_runtime:
            raise RuntimeError(f"missing explicit runtime token {token}")

    for path in sorted((ROOT / "scenes").rglob("*.json")):
        if re.search(r'"model_backbone"\s*:\s*"claudecode"', path.read_text(encoding="utf-8")):
            raise RuntimeError(f"removed backend alias remains in {path.relative_to(ROOT)}")

    print("Strict AgentDef/ContainerAgent contract verified")


def main() -> None:
    patch_scene_def()
    patch_agent_model()
    patch_simulations()
    patch_container_runtime()
    patch_agent_server()
    patch_scene_test()
    patch_container_test()
    patch_agent_model_test()
    migrate_scene_backend_values()
    patch_docs()
    validate()


if __name__ == "__main__":
    main()
