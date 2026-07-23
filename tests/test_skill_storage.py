import json

from agent_network import mcp_server as skill_source
from agent_network.file_management import FileManager
from agent_network.scene_management import SceneStorage


def test_skill_sources_use_managed_scene_resource(tmp_path):
    scenes = tmp_path / 'scenes'
    scene = scenes / 'demo'
    (scene / 'skills/pkg/docs').mkdir(parents=True)
    (scene / 'Agents.json').write_text(
        json.dumps(
            {
                'agents': {
                    'reader': {
                        'name': 'Reader',
                        'role': 'Skill reader',
                        'background': '',
                        'core_goal': 'Read scene skills',
                        'backend': 'openclaw',
                        'skill_refs': ['pkg', 'solo'],
                        'tool_refs': [],
                        'tasks': [],
                    }
                }
            }
        )
    )
    (scene / 'topology.json').write_text(json.dumps({'topology': []}))
    (scene / 'env.py').write_text(
        "ENV = {'metadata': {'title': 'Demo', 'description': ''}, 'environment': {}, 'scene_tasks': []}\n"
    )
    (scene / 'skills/pkg/SKILL.md').write_text('entry')
    (scene / 'skills/pkg/docs/guide.md').write_text('guide')
    (scene / 'skills/solo.md').write_text('solo')
    manager = FileManager({'scenes': scenes}, catalog_path=tmp_path / 'registry.json')
    SceneStorage(manager).get_resource('demo', allow_hidden=True)
    skill_source._TEST_MANAGERS[str(scenes.resolve())] = manager
    assert skill_source.read_scene_skill_file('demo', 'pkg', scenes_root=str(scenes)) == 'entry'
    assert skill_source.list_scene_skill_files('demo', 'pkg', scenes_root=str(scenes)) == ['SKILL.md', 'docs/guide.md']
    assert skill_source.read_scene_skill_file('demo', 'solo', scenes_root=str(scenes)) == 'solo'
