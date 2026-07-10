from dataclasses import dataclass
from pathlib import Path


MAX_SKILL_FILE_BYTES = 512 * 1024


@dataclass(frozen=True)
class SceneSkillSource:
    name: str
    kind: str
    root: Path
    entrypoint: Path

    @property
    def entrypoint_relative(self) -> str:
        if self.kind == "package":
            return self.entrypoint.relative_to(self.root).as_posix()
        return self.entrypoint.name


def _validate_name(value: str, field_name: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{field_name} is required")
    path = Path(value)
    if path.is_absolute() or len(path.parts) != 1 or path.parts[0] in {".", ".."}:
        raise ValueError(f"Invalid {field_name}: {value}")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_scene_skill(
    scene_key: str,
    skill_ref: str,
    scenes_root: str = "/app/scenes",
) -> SceneSkillSource:
    scene_key = _validate_name(scene_key, "scene_key")
    skill_ref = _validate_name(skill_ref, "skill_ref")

    scenes_root_path = Path(scenes_root).resolve()
    scene_root = (scenes_root_path / scene_key).resolve()
    skills_root = (scene_root / "skills").resolve()

    if not _is_within(scene_root, scenes_root_path):
        raise PermissionError("Scene path escaped scenes root")
    if not _is_within(skills_root, scene_root):
        raise PermissionError("Skills path escaped scene root")

    package_root = (skills_root / skill_ref).resolve()
    if package_root.is_dir():
        if not _is_within(package_root, skills_root):
            raise PermissionError("Skill package escaped skills root")
        entrypoint = (package_root / "SKILL.md").resolve()
        if not _is_within(entrypoint, package_root):
            raise PermissionError("Skill entrypoint escaped package root")
        if not entrypoint.is_file():
            raise FileNotFoundError(
                f"Skill package '{skill_ref}' has no SKILL.md entrypoint"
            )
        return SceneSkillSource(
            name=skill_ref,
            kind="package",
            root=package_root,
            entrypoint=entrypoint,
        )

    single_file = (skills_root / f"{skill_ref}.md").resolve()
    if not _is_within(single_file, skills_root):
        raise PermissionError("Skill file escaped skills root")
    if single_file.is_file():
        return SceneSkillSource(
            name=skill_ref,
            kind="file",
            root=skills_root,
            entrypoint=single_file,
        )

    raise FileNotFoundError(
        f"Skill '{skill_ref}' was not found in scene '{scene_key}'"
    )


def describe_scene_skill(
    scene_key: str,
    skill_ref: str,
    scenes_root: str = "/app/scenes",
) -> dict:
    source = resolve_scene_skill(scene_key, skill_ref, scenes_root)
    return {
        "name": source.name,
        "kind": source.kind,
        "entrypoint": source.entrypoint_relative,
    }


def list_scene_skill_files(
    scene_key: str,
    skill_ref: str,
    scenes_root: str = "/app/scenes",
) -> list[str]:
    source = resolve_scene_skill(scene_key, skill_ref, scenes_root)

    if source.kind == "file":
        return [source.entrypoint.name]

    files: list[str] = []
    for path in sorted(source.root.rglob("*")):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if not _is_within(resolved, source.root):
            continue
        files.append(path.relative_to(source.root).as_posix())
    return files


def resolve_scene_skill_file(
    scene_key: str,
    skill_ref: str,
    relative_path: str = "SKILL.md",
    scenes_root: str = "/app/scenes",
) -> Path:
    source = resolve_scene_skill(scene_key, skill_ref, scenes_root)
    requested = str(relative_path or "SKILL.md").strip()
    requested_path = Path(requested)

    if requested_path.is_absolute() or ".." in requested_path.parts:
        raise PermissionError("Skill file path must stay inside the Skill")

    if source.kind == "file":
        allowed_names = {"SKILL.md", source.entrypoint.name, ""}
        if requested not in allowed_names:
            raise FileNotFoundError(
                f"Single-file Skill '{skill_ref}' only exposes its entrypoint"
            )
        return source.entrypoint

    target = (source.root / requested_path).resolve()
    if not _is_within(target, source.root):
        raise PermissionError("Skill file path escaped package root")
    if not target.is_file():
        raise FileNotFoundError(
            f"Skill file '{requested}' was not found in '{skill_ref}'"
        )
    return target


def read_scene_skill_file(
    scene_key: str,
    skill_ref: str,
    relative_path: str = "SKILL.md",
    scenes_root: str = "/app/scenes",
    max_bytes: int = MAX_SKILL_FILE_BYTES,
) -> str:
    path = resolve_scene_skill_file(
        scene_key=scene_key,
        skill_ref=skill_ref,
        relative_path=relative_path,
        scenes_root=scenes_root,
    )
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise ValueError(
            f"Skill file is too large: {len(data)} bytes (limit {max_bytes})"
        )
    return data.decode("utf-8")
