import argparse
import json
import os
from pathlib import Path

from pydantic import Field

from agent_network import mcp_server as base
from agent_network.skill_source import (
    describe_scene_skill,
    list_scene_skill_files,
    read_scene_skill_file,
)


_SCENE_KEY = ""
_SKILL_REFS = set()
_SCENES_ROOT = Path("/app/scenes")


def _skill_allowed(skill_ref: str) -> bool:
    return skill_ref in _SKILL_REFS


def _register_skill_source_tools():
    @base.mcp.tool()
    def list_available_skills() -> str:
        """List Skill sources that the current Agent is allowed to read."""
        items = []
        for skill_ref in sorted(_SKILL_REFS):
            try:
                items.append(
                    describe_scene_skill(
                        scene_key=_SCENE_KEY,
                        skill_ref=skill_ref,
                        scenes_root=str(_SCENES_ROOT),
                    )
                )
            except Exception as exc:
                items.append(
                    {
                        "name": skill_ref,
                        "available": False,
                        "error": str(exc),
                    }
                )
        return json.dumps(items, ensure_ascii=False)

    @base.mcp.tool()
    def list_skill_files(
        skill_ref: str = Field(description="Allowed Skill name"),
    ) -> str:
        """List files inside one allowed Skill package."""
        if not _skill_allowed(skill_ref):
            raise PermissionError(f"Skill is not allowed: {skill_ref}")
        files = list_scene_skill_files(
            scene_key=_SCENE_KEY,
            skill_ref=skill_ref,
            scenes_root=str(_SCENES_ROOT),
        )
        return json.dumps(
            {"skill_ref": skill_ref, "files": files},
            ensure_ascii=False,
        )

    @base.mcp.tool()
    def read_skill_file(
        skill_ref: str = Field(description="Allowed Skill name"),
        relative_path: str = Field(
            default="SKILL.md",
            description="Path relative to the Skill package root",
        ),
    ) -> str:
        """Read one file from an allowed Skill package."""
        if not _skill_allowed(skill_ref):
            raise PermissionError(f"Skill is not allowed: {skill_ref}")
        return read_scene_skill_file(
            scene_key=_SCENE_KEY,
            skill_ref=skill_ref,
            relative_path=relative_path,
            scenes_root=str(_SCENES_ROOT),
        )


def _json_arg(value: str) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def main():
    global _SCENE_KEY, _SKILL_REFS, _SCENES_ROOT

    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--agent-name", default="")
    parser.add_argument("--allowed-tools", default="")
    parser.add_argument("--skill-refs", default="")
    parser.add_argument("--scenes-root", default="/app/scenes")
    parser.add_argument(
        "--agent-directory-json",
        default=os.environ.get("AGENT_DIRECTORY_JSON", "{}"),
    )
    parser.add_argument(
        "--comm-matrix-json",
        default=os.environ.get("COMM_MATRIX_JSON", "{}"),
    )
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--simulation-seed", type=int, default=0)
    args = parser.parse_args()

    _SCENE_KEY = args.scene
    _SKILL_REFS = set(
        args.skill_refs.split(",") if args.skill_refs else []
    )
    _SCENES_ROOT = Path(args.scenes_root)

    base.setup_runtime(
        scene_key=args.scene,
        agent_id=args.agent_id,
        agent_name=args.agent_name or args.agent_id,
        allowed_tools=(
            args.allowed_tools.split(",")
            if args.allowed_tools
            else []
        ),
        scenes_root=args.scenes_root,
        agent_directory=_json_arg(args.agent_directory_json),
        comm_matrix=_json_arg(args.comm_matrix_json),
        trace_id=args.trace_id,
        simulation_seed=args.simulation_seed,
    )
    base.load_tools()
    _register_skill_source_tools()
    base.mcp.run()


if __name__ == "__main__":
    main()
