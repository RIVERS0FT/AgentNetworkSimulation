from __future__ import annotations

import asyncio
import base64
import binascii
import os
import random
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent_network import state
from agent_network.api import simulations as orchestration
from agent_network.capture_management import CaptureConfig, CaptureState, get_capture_coordinator
from agent_network.file_management import FileManagerError, ResourceNotFoundError, ResourceNotReadyError
from agent_network.scene_manager import SceneManager
from agent_network.scene_storage import get_scene_storage

router = APIRouter()
scene_storage = get_scene_storage()


def _scene_is_occupied(scene_key: str) -> bool:
    return bool(state.simulation_active and state.current_scene_name == scene_key)


scene_manager = SceneManager(scene_storage, occupancy_checker=_scene_is_occupied)
captures = get_capture_coordinator()
_active_capture_id = ""


class SimulationRunRequest(BaseModel):
    scene: str = ""
    seed: Optional[int] = None


class SceneBatchUploadItemRequest(BaseModel):
    filename: str
    content_base64: str
    scene_key: str = ""


class SceneBatchUploadRequest(BaseModel):
    items: list[SceneBatchUploadItemRequest] = Field(default_factory=list)


class SceneKeyBatchRequest(BaseModel):
    scene_keys: list[str] = Field(default_factory=list)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ResourceNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (ResourceNotReadyError, RuntimeError)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def _capture_adapter(
    created_cas,
    enabled,
    requests_module,
    session_id: str = "",
    trace_id: str = "",
    network_profiles=None,
):
    del requests_module
    global _active_capture_id
    if enabled:
        targets = []
        for assignment, _ in created_cas:
            if assignment.status == "error" or not assignment.url:
                continue
            targets.append({
                "agent_id": assignment.agent_id,
                "runtime_url": assignment.url,
                "container_id": assignment.container_id,
                "container_name": assignment.container_name,
                "runtime_ip": assignment.container_ip,
            })
        try:
            max_bytes = max(0, int(os.environ.get("PCAP_MAX_BYTES", str(1024 * 1024 * 1024))))
        except ValueError:
            max_bytes = 1024 * 1024 * 1024
        session = captures.create_session(
            simulation_id=session_id,
            session_id=session_id,
            trace_id=trace_id,
            capture_id=session_id,
            targets=targets,
            config=CaptureConfig(
                interface="any",
                max_bytes=max_bytes,
                include_control_plane=os.environ.get("AGENT_CAPTURE_INCLUDE_CONTROL_PLANE", "0") == "1",
            ),
        )
        for agent_id, profiles in (network_profiles or {}).items():
            if agent_id in session.targets:
                session.targets[agent_id].details["network_profiles"] = profiles
        session = captures.start_session(session.capture_id)
        _active_capture_id = session.capture_id
    else:
        capture_id = _active_capture_id or session_id
        try:
            session = captures.stop_session(capture_id, "simulation_finished")
        except KeyError:
            return {"success": 0, "failed": 0, "agents": [], "status": "not_running"}
        _active_capture_id = ""
    agents = [target.to_dict() for target in session.targets.values()]
    success = sum(1 for target in session.targets.values() if target.state in {CaptureState.RUNNING, CaptureState.STOPPED})
    failed = len(session.targets) - success
    return {
        "capture_id": session.capture_id,
        "status": session.state.value,
        "success": success,
        "failed": failed,
        "agents": agents,
    }


def _capture_health_adapter(created_cas, requests_module):
    del created_cas, requests_module
    if not _active_capture_id:
        return {"healthy": False, "failed": 1, "agents": [], "status": "not_running"}
    try:
        session = captures.check_health(_active_capture_id)
    except KeyError:
        return {"healthy": False, "failed": 1, "agents": [], "status": "not_found"}
    agents = [target.to_dict() for target in session.targets.values()]
    failed = sum(1 for target in session.targets.values() if target.state != CaptureState.RUNNING)
    return {
        "capture_id": session.capture_id,
        "healthy": session.state == CaptureState.RUNNING and failed == 0,
        "failed": failed,
        "agents": agents,
    }


# The legacy orchestration module owns simulation execution for now, but its
# capture hooks are replaced by the single CaptureManager control-plane entry.
orchestration._capture = _capture_adapter
orchestration._capture_health = _capture_health_adapter


@router.post("/simulations/setup")
async def setup_simulation(req: SimulationRunRequest):
    if not req.scene:
        raise HTTPException(status_code=400, detail="scene is required")
    try:
        scene_def = scene_manager.build_definition(req.scene)
    except (ValueError, OSError, FileManagerError) as exc:
        raise _http_error(exc) from exc
    if req.seed is None:
        configured_seed = os.environ.get("SIMULATION_SEED", "").strip()
        pending_seed = int(configured_seed) if configured_seed else random.SystemRandom().randrange(1, 2 ** 31)
    else:
        pending_seed = req.seed
    random.seed(pending_seed)
    orchestration._pending_seed = pending_seed
    orchestration._pending_config = orchestration._get_effective_llm_config()
    state.current_scene_name = scene_def.scene_key
    state.active_tools_module = None
    result = orchestration._setup_scene(scene_def)
    state.current_topology = result["topology"]
    return result


@router.post("/simulations/launch")
async def launch_simulation():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        orchestration._launch_containers,
        orchestration._pending_config,
        orchestration._pending_scene_def,
    )


@router.post("/simulations/stop")
async def stop_simulation():
    state.simulation_stop_requested = True
    return {"status": "stop_requested"}


@router.get("/scenes")
async def list_scenes(include_hidden: bool = Query(default=False)):
    return {"scenes": scene_manager.list_scenes(include_hidden=include_hidden)}


@router.get("/scenes/state")
async def scene_state():
    return {
        "scene": state.current_scene_name,
        "running": state.simulation_active,
        "agents": [agent.get_status() for agent in orchestration.AgentRegistry.list_all()],
        "custom": None,
    }


@router.post("/scenes/upload")
async def upload_scene(request: Request, filename: str = Query(...), scene_key: str = Query(default="")):
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="empty upload")
    try:
        return scene_manager.upload_one(filename=filename, content=content, scene_key=scene_key)
    except (ValueError, OSError, FileManagerError) as exc:
        raise _http_error(exc) from exc


@router.post("/scenes/batch/upload")
async def batch_upload_scenes(req: SceneBatchUploadRequest):
    prepared = []
    for item in req.items:
        try:
            content = base64.b64decode(item.content_base64, validate=True)
            prepared.append({
                "filename": item.filename,
                "scene_key": item.scene_key,
                "content": content,
            })
        except (binascii.Error, ValueError) as exc:
            prepared.append({
                "filename": item.filename,
                "scene_key": item.scene_key,
                "error_code": "invalid_base64",
                "error": str(exc),
            })
    result = await asyncio.to_thread(scene_manager.upload_many, prepared)
    return result.to_dict()


@router.post("/scenes/batch/download")
async def batch_download_scenes(req: SceneKeyBatchRequest):
    result = await asyncio.to_thread(scene_manager.download_many, req.scene_keys)
    payload = result.to_dict()
    if result.archive_resource_id:
        payload["download_url"] = f"/api/scenes/batch/download/{result.archive_resource_id}"
    return payload


@router.get("/scenes/batch/download/{resource_id}")
async def download_scene_batch(resource_id: str):
    try:
        descriptor = scene_manager.prepare_batch_download(resource_id)
    except (ValueError, OSError, FileManagerError) as exc:
        raise _http_error(exc) from exc
    return FileResponse(
        descriptor.internal_path,
        media_type=descriptor.media_type,
        filename=descriptor.logical_name,
    )


@router.post("/scenes/batch/delete")
async def batch_delete_scenes(req: SceneKeyBatchRequest):
    result = await asyncio.to_thread(scene_manager.delete_many, req.scene_keys)
    return result.to_dict()


@router.post("/scenes/batch/parse")
async def batch_parse_scenes(req: SceneKeyBatchRequest):
    result = await asyncio.to_thread(scene_manager.parse_many, req.scene_keys)
    return result.to_dict()


@router.get("/scenes/{scene_key}/download")
async def download_scene(scene_key: str):
    try:
        archive = scene_manager.create_archive(scene_key)
        descriptor = scene_manager.files.prepare_download(archive.resource_id)
    except (ValueError, OSError, FileManagerError) as exc:
        raise _http_error(exc) from exc
    return FileResponse(descriptor.internal_path, media_type=descriptor.media_type, filename=descriptor.logical_name)


@router.post("/scenes/{scene_key}/hide")
async def hide_scene(scene_key: str):
    try:
        resource = scene_manager.set_visibility(scene_key, False)
    except (ValueError, OSError, FileManagerError) as exc:
        raise _http_error(exc) from exc
    return resource.to_dict()


@router.post("/scenes/{scene_key}/show")
async def show_scene(scene_key: str):
    try:
        resource = scene_manager.set_visibility(scene_key, True)
    except (ValueError, OSError, FileManagerError) as exc:
        raise _http_error(exc) from exc
    return resource.to_dict()


@router.delete("/scenes/{scene_key}")
async def delete_scene(scene_key: str):
    try:
        resource = scene_manager.delete_one(scene_key)
    except (ValueError, OSError, RuntimeError, FileManagerError) as exc:
        raise _http_error(exc) from exc
    return resource.to_dict()


@router.get("/scenes/{scene_key}")
async def read_scene(scene_key: str):
    try:
        return scene_manager.details(scene_key)
    except (ValueError, OSError, FileManagerError) as exc:
        raise _http_error(exc) from exc
