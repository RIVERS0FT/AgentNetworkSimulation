#!/usr/bin/env python3
"""Extract AgentDef-compatible agents.json files from scene role/instance configs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCENES_DIR = ROOT / "scenes"


def _string_list(value: Any, *, field: str, scene: Path, agent_id: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{scene}: agent {agent_id!r} field {field!r} must be an array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"{scene}: agent {agent_id!r} field {field!r} must contain non-empty strings"
            )
        normalized = item.strip()
        if normalized not in result:
            result.append(normalized)
    return result


def _build_agents(scene_dir: Path) -> dict[str, list[dict[str, Any]]]:
    meta_path = scene_dir / "meta_and_roles.json"
    instances_path = scene_dir / "instances_and_skills.json"

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    instances = json.loads(instances_path.read_text(encoding="utf-8"))
    roles = meta.get("roles")
    containers = instances.get("container_instances")

    if not isinstance(roles, dict):
        raise ValueError(f"{meta_path}: root field 'roles' must be an object")
    if not isinstance(containers, dict):
        raise ValueError(f"{instances_path}: root field 'container_instances' must be an object")

    agents: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for role_id, role_config in roles.items():
        if not isinstance(role_config, dict):
            raise ValueError(f"{meta_path}: role {role_id!r} must be an object")

        agent_id = str(role_id).strip().lower()
        if not agent_id:
            raise ValueError(f"{meta_path}: role id must be non-empty")
        if agent_id in seen_ids:
            raise ValueError(f"{meta_path}: duplicate normalized agent_id {agent_id!r}")
        seen_ids.add(agent_id)

        instance = containers.get(role_id, {})
        if not isinstance(instance, dict):
            raise ValueError(f"{instances_path}: container instance {role_id!r} must be an object")

        name = str(role_config.get("name") or role_id)
        role = str(role_config.get("identity") or name)
        background = str(role_config.get("background") or "")
        core_goal = str(role_config.get("core_goal") or "")
        backend = str(role_config.get("model_backbone") or "openclaw").strip()

        skill_refs_value = instance.get("skill_refs")
        if skill_refs_value is None:
            skill_refs_value = instance.get("skills")
        allowed_tools_value = instance.get("tool_refs")
        if allowed_tools_value is None:
            allowed_tools_value = instance.get("allowed_tools")

        agents.append(
            {
                "agent_id": agent_id,
                "role": role,
                "name": name,
                "background": background,
                "core_goal": core_goal,
                "backend": backend,
                "skill_refs": _string_list(
                    skill_refs_value,
                    field="skill_refs",
                    scene=scene_dir,
                    agent_id=agent_id,
                ),
                "allowed_tools": _string_list(
                    allowed_tools_value,
                    field="allowed_tools",
                    scene=scene_dir,
                    agent_id=agent_id,
                ),
                "tasks": _string_list(
                    instance.get("tasks"),
                    field="tasks",
                    scene=scene_dir,
                    agent_id=agent_id,
                ),
            }
        )

    unknown_instances = sorted(set(containers) - set(roles))
    if unknown_instances:
        raise ValueError(
            f"{instances_path}: container instances reference unknown roles: {unknown_instances}"
        )

    return {"agents": agents}


def extract(*, check: bool = False) -> tuple[int, int]:
    scene_dirs = sorted(
        path.parent
        for path in SCENES_DIR.rglob("meta_and_roles.json")
        if (path.parent / "instances_and_skills.json").is_file()
    )
    if not scene_dirs:
        raise RuntimeError("No scene directories with role and instance configuration were found")

    changed = 0
    total_agents = 0
    for scene_dir in scene_dirs:
        payload = _build_agents(scene_dir)
        total_agents += len(payload["agents"])
        rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        target = scene_dir / "agents.json"
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current != rendered:
            changed += 1
            if check:
                raise SystemExit(f"Outdated or missing file: {target.relative_to(ROOT)}")
            target.write_text(rendered, encoding="utf-8")
            print(f"generated {target.relative_to(ROOT)} ({len(payload['agents'])} agents)")

    print(f"processed {len(scene_dirs)} scenes, {total_agents} agents, {changed} files changed")
    return len(scene_dirs), total_agents


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when generated files are missing or stale")
    args = parser.parse_args()
    extract(check=args.check)


if __name__ == "__main__":
    main()
