"""Non-secret launcher preferences needed before the database is unlocked."""
import json
import os
from pathlib import Path
import socket
import tempfile
import ipaddress
from fastapi import APIRouter,Depends,Request
from pydantic import BaseModel,ConfigDict,Field
from backend.auth import authenticated_actor
from backend.local_auth import admin,csrf
from backend.errors import AccessError

router=APIRouter(prefix='/api/v1/settings/runtime')
class RuntimePreferences(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    network_available:bool=False
    port:int=Field(default=8000,ge=1,le=65535)
    minimize_to_tray:bool=True

def load(database,default_port=8000):
    path=Path(database).resolve().parent/'launcher.json'
    try:
        if path.is_symlink():return RuntimePreferences(port=default_port)
        return RuntimePreferences.model_validate_json(path.read_bytes())
    except (OSError,ValueError):return RuntimePreferences(port=default_port)

def save(database,preferences):
    path=Path(database).resolve().parent/'launcher.json'
    if path.is_symlink():raise AccessError(409,'INVALID_CONFIG','Launcher settings are unavailable.')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temporary=tempfile.mkstemp(prefix='.launcher-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(preferences.model_dump_json());stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        Path(temporary).unlink(missing_ok=True)

def valid_host(request,network):
    try:
        host=(request.url.hostname or '').lower();_=request.url.port
    except ValueError:return False
    if host in ('localhost','127.0.0.1','::1'):return True
    if not network:return False
    # Literal addresses must match this connection's local destination. A Host
    # header for an arbitrary website cannot turn LAN exposure into DNS rebinding.
    server=request.scope.get('server') or ('',0)
    try:
        return ipaddress.ip_address(host)==ipaddress.ip_address(server[0]) and not ipaddress.ip_address(host).is_unspecified
    except ValueError:
        name=socket.gethostname().lower()
        return host in (name,name+'.local')

def administrator(request:Request):
    actor=authenticated_actor(request)
    if request.app.state.local_auth:admin(actor)

def status(request):
    state=request.app.state
    running_port=getattr(state,'listen_port',None) or request.url.port or 8000
    preferences=load(state.database.path,running_port)
    network=getattr(state,'network_available',False)
    return {**preferences.model_dump(),'running_port':running_port,'network_active':network,
        'tray_supported':bool(os.name=='nt' and os.environ.get('EVORA_NATIVE_WINDOW')=='1'),
        'restart_required':preferences.port!=running_port or preferences.network_available!=network}

@router.get('',operation_id='getRuntimeSettings',dependencies=[Depends(administrator)])
def get_settings(request:Request):return status(request)

@router.put('',operation_id='updateRuntimeSettings',dependencies=[Depends(administrator),Depends(csrf)])
def put_settings(body:RuntimePreferences,request:Request):
    save(request.app.state.database.path,body)
    return status(request)
