from __future__ import annotations
import asyncio
import os
import random
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agent_network import state
from agent_network.api import simulations as orchestration
from agent_network.file_management import FileManagerError, ResourceNotFoundError, ResourceNotReadyError
from agent_network.scene_storage import get_scene_storage
router = APIRouter(); scene_storage = get_scene_storage()

class SimulationRunRequest(BaseModel):
    scene: str = ''
    seed: Optional[int] = None

def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ResourceNotFoundError): return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ResourceNotReadyError): return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))

@router.post('/simulations/setup')
async def setup_simulation(req: SimulationRunRequest):
    if not req.scene: raise HTTPException(status_code=400, detail='scene is required')
    try: scene_def = scene_storage.build_definition(req.scene)
    except (ValueError, OSError, FileManagerError) as exc: raise _http_error(exc) from exc
    if req.seed is None:
        configured_seed = os.environ.get('SIMULATION_SEED', '').strip(); pending_seed = int(configured_seed) if configured_seed else random.SystemRandom().randrange(1, 2 ** 31)
    else: pending_seed = req.seed
    random.seed(pending_seed); orchestration._pending_seed = pending_seed; orchestration._pending_config = orchestration._get_effective_llm_config(); state.current_scene_name = scene_def.scene_key; state.active_tools_module = None
    result = orchestration._setup_scene(scene_def); state.current_topology = result['topology']; return result

@router.post('/simulations/launch')
async def launch_simulation():
    loop = asyncio.get_running_loop(); return await loop.run_in_executor(None, orchestration._launch_containers, orchestration._pending_config, orchestration._pending_scene_def)

@router.post('/simulations/stop')
async def stop_simulation():
    state.simulation_stop_requested = True; return {'status': 'stop_requested'}

@router.get('/scenes')
async def list_scenes(include_hidden: bool=Query(default=False)):
    return {'scenes': scene_storage.list_scenes(include_hidden=include_hidden)}

@router.get('/scenes/state')
async def scene_state():
    return {'scene': state.current_scene_name, 'running': state.simulation_active, 'agents': [agent.get_status() for agent in orchestration.AgentRegistry.list_all()], 'custom': None}

@router.post('/scenes/upload')
async def upload_scene(request: Request, filename: str=Query(...), scene_key: str=Query(default='')):
    content = await request.body()
    if not content: raise HTTPException(status_code=400, detail='empty upload')
    try: return scene_storage.import_archive(filename=filename, content=content, scene_key=scene_key)
    except (ValueError, OSError, FileManagerError) as exc: raise _http_error(exc) from exc

@router.get('/scenes/{scene_key}/download')
async def download_scene(scene_key: str):
    try: archive = scene_storage.create_archive(scene_key); descriptor = scene_storage.files.prepare_download(archive.resource_id)
    except (ValueError, OSError, FileManagerError) as exc: raise _http_error(exc) from exc
    return FileResponse(descriptor.internal_path, media_type=descriptor.media_type, filename=descriptor.logical_name)

@router.post('/scenes/{scene_key}/hide')
async def hide_scene(scene_key: str):
    try: resource = scene_storage.set_visibility(scene_key, False)
    except (ValueError, OSError, FileManagerError) as exc: raise _http_error(exc) from exc
    return resource.to_dict()

@router.post('/scenes/{scene_key}/show')
async def show_scene(scene_key: str):
    try: resource = scene_storage.set_visibility(scene_key, True)
    except (ValueError, OSError, FileManagerError) as exc: raise _http_error(exc) from exc
    return resource.to_dict()

@router.delete('/scenes/{scene_key}')
async def delete_scene(scene_key: str):
    if state.simulation_active and state.current_scene_name == scene_key: raise HTTPException(status_code=409, detail='Scene is used by an active simulation')
    try: resource = scene_storage.delete(scene_key)
    except (ValueError, OSError, FileManagerError) as exc: raise _http_error(exc) from exc
    return resource.to_dict()

@router.get('/scenes/{scene_key}')
async def read_scene(scene_key: str):
    try: return scene_storage.details(scene_key)
    except (ValueError, OSError, FileManagerError) as exc: raise _http_error(exc) from exc
