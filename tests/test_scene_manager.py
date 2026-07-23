import io
import json
import zipfile

import pytest

from agent_network.file_management import FileManager, ResourceNotFoundError
from agent_network.scene_management import SceneManager, SceneStorage


def _scene_zip(title: str, agent_id: str = "planner") -> bytes:
    payload = io.BytesIO()
    agents = {
        "agents": {
            agent_id: {
                "name": agent_id.title(),
                "role": f"{agent_id} identity",
                "background": "",
                "core_goal": "Complete assigned work",
                "backend": "openclaw",
                "skill_refs": [],
                "tool_refs": [],
                "tasks": [
                    {
                        "task_id": f"{agent_id}-task",
                        "goal": "execute task",
                        "input": {},
                        "depends_on": [],
                    }
                ],
            }
        }
    }
    topology = {"topology": []}
    env = f"""ENV = {{
    'metadata': {{'title': {title!r}, 'description': {f'{title} description'!r}}},
    'environment': {{'global_rules': [{f'{title} rules'!r}], 'initial_state': {{}}, 'shared_data': {{}}}},
    'scene_tasks': [
        {{'task_id': 'scene-complete', 'goal': 'Complete scene', 'input': {{}}, 'depends_on': [{f'{agent_id}-task'!r}]}}
    ],
}}
"""
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("Agents.json", json.dumps(agents))
        archive.writestr("topology.json", json.dumps(topology))
        archive.writestr("env.py", env)
    return payload.getvalue()


@pytest.fixture
def manager(tmp_path):
    files = FileManager(
        {
            "scenes": tmp_path / "scenes",
            "archives": tmp_path / "archives",
            "temp": tmp_path / "temp",
        },
        catalog_path=tmp_path / "registry.json",
    )
    occupied = {"busy"}
    return SceneManager(
        SceneStorage(files),
        occupancy_checker=lambda scene_key: scene_key in occupied,
    )


def test_batch_upload_isolates_invalid_items(manager):
    result = manager.upload_many(
        [
            {
                "filename": "alpha.zip",
                "scene_key": "alpha",
                "content": _scene_zip("Alpha"),
            },
            {
                "filename": "broken.zip",
                "scene_key": "broken",
                "content": b"not-a-zip",
            },
        ]
    )

    assert result.total == 2
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.items[0].status == "uploaded"
    assert result.items[1].success is False
    assert manager.details("alpha")["title"] == "Alpha"


def test_batch_parse_returns_each_definition(manager):
    manager.upload_one(
        filename="alpha.zip",
        scene_key="alpha",
        content=_scene_zip("Alpha"),
    )

    result = manager.parse_many(["alpha", "missing"])

    assert result.succeeded == 1
    assert result.failed == 1
    definition = result.items[0].details["definition"]
    assert definition["scene_key"] == "alpha"
    assert definition["agents"][0]["agent_id"] == "planner"
    assert definition["environment"]["global_rules"] == ["Alpha rules"]
    assert result.items[1].error_code == "scene_not_found"


def test_scene_list_and_details_use_the_v2_domain_contract(manager):
    manager.upload_one(
        filename="alpha.zip",
        scene_key="alpha",
        content=_scene_zip("Alpha"),
    )

    assert manager.list_scenes() == [{"scene_key": "alpha", "title": "Alpha"}]
    details = manager.details("alpha")
    assert set(details) == {
        "scene_key",
        "title",
        "description",
        "environment",
        "agents",
        "skills",
        "tools",
        "tasks",
        "topology",
        "validation",
    }
    assert details["environment"]["global_rules"] == ["Alpha rules"]
    assert details["validation"]["validation_status"] == "fully_validated"
    assert details["validation"]["schema_version"] == "agentnetwork-scene.v2"
    assert "raw" not in details
    assert "resource_id" not in details


def test_invalid_scene_upload_is_rolled_back(manager):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("Agents.json", json.dumps({"agents": {}}))
        archive.writestr("topology.json", json.dumps({"topology": []}))
        archive.writestr(
            "env.py",
            "ENV = {'metadata': {'title': 'Invalid', 'description': ''}, 'environment': {}, 'scene_tasks': []}\n",
        )

    result = manager.upload_many(
        [{"filename": "invalid.zip", "scene_key": "invalid", "content": payload.getvalue()}]
    )

    assert result.failed == 1
    assert manager.list_scenes() == []


def test_batch_download_creates_one_managed_archive(manager):
    manager.upload_one(
        filename="alpha.zip",
        scene_key="alpha",
        content=_scene_zip("Alpha"),
    )
    manager.upload_one(
        filename="beta.zip",
        scene_key="beta",
        content=_scene_zip("Beta", agent_id="operator"),
    )

    result = manager.download_many(["alpha", "beta", "missing"])

    assert result.succeeded == 2
    assert result.failed == 1
    assert result.archive_resource_id
    descriptor = manager.prepare_batch_download(result.archive_resource_id)
    with zipfile.ZipFile(descriptor.internal_path) as archive:
        names = set(archive.namelist())
    assert "alpha/Agents.json" in names
    assert "alpha/env.py" in names
    assert "beta/topology.json" in names


def test_batch_delete_checks_occupancy_per_item(manager):
    manager.upload_one(
        filename="busy.zip",
        scene_key="busy",
        content=_scene_zip("Busy"),
    )
    manager.upload_one(
        filename="free.zip",
        scene_key="free",
        content=_scene_zip("Free"),
    )

    result = manager.delete_many(["busy", "free"])

    assert result.succeeded == 1
    assert result.failed == 1
    assert result.items[0].status == "blocked"
    assert result.items[0].error_code == "scene_in_use"
    assert manager.details("busy")["scene_key"] == "busy"
    with pytest.raises(ResourceNotFoundError):
        manager.storage.get_resource("free")
