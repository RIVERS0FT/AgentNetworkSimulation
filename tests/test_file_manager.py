import io
import json
import zipfile

import pytest

from agent_network.file_management import FileManager, ResourceNotReadyError, UnsafePathError, stable_resource_id

@pytest.fixture
def manager(tmp_path):
    roots = {'scenes': tmp_path / 'scenes', 'logs': tmp_path / 'logs', 'pcap': tmp_path / 'pcap', 'archives': tmp_path / 'archives', 'temp': tmp_path / 'temp'}
    return FileManager(roots, catalog_path=tmp_path / 'file_registry.json')

def test_write_read_visibility_download_and_delete(manager):
    resource = manager.write_text('hello\n', owner_type='log_session', owner_id='session-1', resource_type='application_log', root_name='logs', relative_path='session-1/application.jsonl', logical_name='application.jsonl', media_type='application/x-ndjson')
    assert manager.read_text(resource.resource_id) == 'hello\n'; manager.append_text(resource.resource_id, 'world\n'); assert manager.read_text(resource.resource_id) == 'hello\nworld\n'; manager.set_visibility([resource.resource_id], False); assert manager.list_resources() == []
    with pytest.raises(ResourceNotReadyError): manager.prepare_download(resource.resource_id)
    manager.set_visibility([resource.resource_id], True); assert manager.prepare_download(resource.resource_id).sha256; manager.delete([resource.resource_id]); assert manager.list_resources(include_hidden=True) == []

def test_directory_child_and_tree_manifest(manager):
    scene = manager.ensure_directory(owner_type='scene', owner_id='demo', resource_type='scene_directory', root_name='scenes', relative_path='demo', resource_id=stable_resource_id('scene', 'demo'))
    path = manager.resolve_resource_path(scene.resource_id); (path / 'meta.json').write_text('{"name": "demo"}', encoding='utf-8'); manager.refresh(scene.resource_id)
    assert manager.read_child_json(scene.resource_id, 'meta.json') == {'name': 'demo'}; manifest = manager.tree_manifest(scene.resource_id); assert manifest['files'][0]['path'] == 'meta.json'; assert manifest['sha256']

def test_create_archive_with_virtual_files(manager):
    first = manager.write_text('one', owner_type='log_session', owner_id='session-1', resource_type='application_log', root_name='logs', relative_path='session-1/application.jsonl', logical_name='application.jsonl')
    archive = manager.create_archive([first.resource_id], owner_type='simulation', owner_id='session-1', root_name='archives', relative_path='session-1.zip', archive_names={first.resource_id: 'logs/application.jsonl'}, virtual_files={'quality.json': json.dumps({'passed': True})})
    with zipfile.ZipFile(manager.resolve_resource_path(archive.resource_id)) as bundle: assert set(bundle.namelist()) == {'logs/application.jsonl', 'quality.json'}

def test_extract_rejects_path_traversal(manager):
    archive_path = manager.resolve_path('archives', 'unsafe.zip'); payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w') as archive: archive.writestr('../escape.txt', 'bad')
    archive_path.write_bytes(payload.getvalue()); resource = manager.register_existing(owner_type='system', owner_id='test', resource_type='archive', root_name='archives', relative_path='unsafe.zip')
    with pytest.raises(UnsafePathError): manager.extract_archive(resource.resource_id, destination_root_name='temp', destination_relative_dir='unsafe')

def test_two_manager_instances_merge_catalog_updates(tmp_path):
    roots = {'logs': tmp_path / 'logs', 'pcap': tmp_path / 'pcap', 'scenes': tmp_path / 'scenes', 'archives': tmp_path / 'archives', 'temp': tmp_path / 'temp'}; catalog = tmp_path / 'file_registry.json'; first = FileManager(roots, catalog_path=catalog); second = FileManager(roots, catalog_path=catalog)
    a = first.write_text('a', owner_type='system', owner_id='one', resource_type='text', root_name='logs', relative_path='a.txt'); b = second.write_text('b', owner_type='system', owner_id='two', resource_type='text', root_name='logs', relative_path='b.txt')
    assert {item.resource_id for item in first.list_resources()} == {a.resource_id, b.resource_id}
