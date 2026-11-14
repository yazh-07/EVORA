"""Official release checks and resumable, checksum-verified Windows updates."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from backend.auth import authenticated_actor
from backend.chatgpt_connection import tls_context
from backend.errors import AccessError
from backend.local_auth import admin, csrf
from backend.version import APP_VERSION
from backend import incremental as inc

REPOSITORY='https://github.com/yazh-07/EVORA'
LATEST='https://api.github.com/repos/yazh-07/EVORA/releases/latest'
INSTALLER='EVORA-Setup-Windows-x64.exe'
MAX_DOWNLOAD=2*1024**3
router=APIRouter(prefix='/api/v1/updates')


class UpdateError(ValueError):
    pass


def version(value):
    match=re.fullmatch(r'v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)',value or '')
    if not match:raise UpdateError('The release version is not supported.')
    return tuple(int(part) for part in match.groups())


def client():
    return httpx.Client(verify=tls_context(),timeout=httpx.Timeout(30,connect=5),trust_env=False,
        follow_redirects=False,headers={'User-Agent':'EVORA/'+APP_VERSION,'Accept':'application/vnd.github+json'})


@contextmanager
def remote(http,url,headers=None):
    for _ in range(6):
        parsed=urlsplit(url)
        if (parsed.scheme!='https' or parsed.hostname not in {'api.github.com','github.com',
                'release-assets.githubusercontent.com','objects.githubusercontent.com'} or parsed.username or
                parsed.password or parsed.port not in (None,443) or parsed.fragment):
            raise UpdateError('The update download destination is not trusted.')
        with http.stream('GET',url,headers=headers) as response:
            if response.status_code in (301,302,303,307,308):
                url=urljoin(url,response.headers.get('Location',''))
                continue
            response.raise_for_status()
            yield response
            return
    raise UpdateError('The update download redirected too many times.')


def read_remote(http,url,limit):
    data=bytearray()
    with remote(http,url) as response:
        for chunk in response.iter_bytes(65536):
            data.extend(chunk)
            if len(data)>limit:raise UpdateError('The update response exceeded its size limit.')
    return bytes(data)


def parse_release(body,current,asset_name):
    if not isinstance(body,dict) or body.get('draft') or body.get('prerelease'):
        raise UpdateError('A stable release could not be found.')
    tag=body.get('tag_name')
    if not isinstance(tag,str):raise UpdateError('The release version is missing.')
    newer=version(tag)>version(current)
    assets=body.get('assets',[])
    if not isinstance(assets,list):raise UpdateError('The release files could not be read.')
    selected=next((item for item in assets if isinstance(item,dict) and item.get('name')==asset_name),None)
    checksum=next((item for item in assets if isinstance(item,dict) and item.get('name')=='SHA256SUMS'),None)
    extra={name:next((item for item in assets if isinstance(item,dict) and item.get('name')==name),None) for name in (inc.MANIFEST,inc.BUNDLE)}
    for item,name in [(selected,asset_name),(checksum,'SHA256SUMS'),*((item,name) for name,item in extra.items())]:
        if item and item.get('browser_download_url')!=f'{REPOSITORY}/releases/download/{tag}/{name}':
            raise UpdateError('The release file is not hosted in the EVORA repository.')
    if selected and (type(selected.get('size')) is not int or not 0<selected['size']<=MAX_DOWNLOAD):
        raise UpdateError('The update file size is invalid.')
    for name,item in extra.items():
        if item and (type(item.get('size')) is not int or not 0<item['size']<=(inc.MAX_MANIFEST if name==inc.MANIFEST else MAX_DOWNLOAD)):
            raise UpdateError('The incremental update size is invalid.')
    return dict(tag=tag,newer=newer,asset=selected,checksum=checksum,incremental=extra,
        release_url=f'{REPOSITORY}/releases/tag/{tag}')


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


class Updates:
    def __init__(self,app,*,current=APP_VERSION,can_install=None,cache=None,installed_root=None):
        self.app=app;self.current=current
        self.can_install=(sys.platform=='win32' and bool(getattr(sys,'frozen',False))) if can_install is None else can_install
        self.platform='windows' if sys.platform=='win32' else 'linux' if sys.platform.startswith('linux') else 'other'
        self.asset_name=INSTALLER if self.platform=='windows' or self.can_install else (
            'evora-linux-x86_64.tar.gz' if self.platform=='linux' and platform.machine().lower() in ('x86_64','amd64') else None)
        self.cache=Path(cache) if cache else app.state.database.path.parent/'updates'
        self.lock=threading.RLock();self.stop=threading.Event();self.release=None;self.expected=None;self.installer=None;self.last_check=0
        self.root=Path(installed_root).resolve() if installed_root else (Path(sys.executable).resolve().parent.parent if self.can_install and Path(sys.executable).parent.name.lower()=='backend' else None)
        self.incremental=None;self.helper_process=False
        self.state=dict(mode='installer',file_count=0,current_version=current,latest_version=None,status='idle',downloaded_bytes=0,total_bytes=0,
            release_url=REPOSITORY+'/releases/latest',download_url=None,checked_at=None,error=None)

    def status(self):
        with self.lock:
            if self.installer is not None and self.installer.poll() is not None:
                code=self.installer.returncode;self.installer=None
                if self.helper_process:
                    self._fallback('The update could not finish. Download the installer to continue.')
                    self.helper_process=False
                else:self.state.update(status='ready',error='Installation did not finish. Try again.' if code else None)
            return {**self.state,'automatic':self.app.state.automatic_update_checks,'can_install':self.can_install,
                'available':bool(self.release and self.release['newer'])}

    def set(self,**values):
        with self.lock:self.state.update(values)

    def check(self,automatic=False):
        with self.lock:
            if self.state['status'] in ('checking','downloading','installing'):return self.status()
            if automatic and (not self.app.state.automatic_update_checks or (self.last_check and time.monotonic()-self.last_check<21600)):return self.status()
            self.last_check=time.monotonic()
            self.state.update(status='checking',error=None)
            threading.Thread(target=self._check,daemon=True).start()
            return self.status()

    def _check(self):
        try:
            self._prune_cache()
            with client() as http:
                body=json.loads(read_remote(http,LATEST,2*1024*1024))
                release=parse_release(body,self.current,self.asset_name)
                self.incremental=None;self.expected=None
                if release['newer'] and self.can_install and self.root and release['asset'] and release['checksum'] and all(release['incremental'].values()):
                    try:self.incremental=self._prepare_incremental(http,release)
                    except (ValueError,OSError,KeyError,TypeError,httpx.HTTPError):pass
            with self.lock:
                self.release=release
                asset=release['asset']
                package=self.incremental
                self.state.update(status='available' if release['newer'] else 'up_to_date',latest_version=release['tag'].lstrip('v'),
                    mode='incremental' if package else 'installer',file_count=len(package['changes']) if package else 0,
                    download_url=release['incremental'][inc.BUNDLE]['browser_download_url'] if package else asset['browser_download_url'] if asset else None,
                    total_bytes=package['total'] if package else asset['size'] if asset else 0,
                    downloaded_bytes=0,release_url=release['release_url'],checked_at=datetime.now(timezone.utc).isoformat(),error=None)
        except UpdateError as error:self.set(status='error',error=str(error))
        except (httpx.HTTPError,ValueError,OSError,TypeError):self.set(status='error',error='Could not check for updates. Check your connection and retry.')

    def _prune_cache(self):
        # Remove only updater-owned files from completed versions. Never prune
        # a stage while its helper or recovery journal may still be using it.
        if not self.root or (self.root/'.evora-update-journal').exists() or not self.cache.is_dir():return
        if self.cache.is_symlink() or (hasattr(self.cache,'is_junction') and self.cache.is_junction()):return
        for path in self.cache.iterdir():
            match=re.fullmatch(r'(v?\d+\.\d+\.\d+)-(incremental|'+re.escape(INSTALLER)+r'(?:\.part)?)',path.name)
            if not match or version(match[1])>version(self.current):continue
            if path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):continue
            try:
                if match[2]=='incremental' and path.is_dir():shutil.rmtree(path)
                elif path.is_file():path.unlink()
            except OSError:pass  # A still-running bootstrap is retried next check.

    def _private_cache(self):
        if self.cache.is_symlink() or (hasattr(self.cache,'is_junction') and self.cache.is_junction()):raise UpdateError('The update folder is not available.')
        self.cache.mkdir(mode=0o700,parents=True,exist_ok=True)
        if os.name=='nt':
            from backend.windows_credentials import secure_path
            secure_path(self.cache,directory=True)
        else:os.chmod(self.cache,0o700)

    def _paths(self):
        self._private_cache()
        target=self.cache/(self.release['tag']+'-'+INSTALLER)
        partial=target.with_suffix('.exe.part')
        if target.is_symlink() or partial.is_symlink():raise UpdateError('The update file is not available.')
        return target,partial

    def _stage(self,tag):
        # Reuse the same private, ACL-protected cache as installer downloads.
        self._private_cache()
        stage=self.cache/(tag+'-incremental')
        if stage.is_symlink() or (hasattr(stage,'is_junction') and stage.is_junction()):raise UpdateError('Invalid update folder.')
        stage.mkdir(mode=0o700,exist_ok=True)
        if os.name=='nt':
            from backend.windows_credentials import secure_path
            secure_path(stage,directory=True)
        for name in ('objects','payload','manifest.json','plan.json','bootstrap.exe','result.json','health.json'):
            child=stage/name
            if child.is_symlink() or (hasattr(child,'is_junction') and child.is_junction()):raise UpdateError('Linked update folders are not supported.')
        return stage.resolve()

    @staticmethod
    def _checksum(http,release,name):
        text=read_remote(http,release['checksum']['browser_download_url'],65536).decode('ascii')
        matches=re.findall(r'^([a-fA-F0-9]{64})[ \t]+\*?'+re.escape(name)+r'\r?$',text,re.MULTILINE)
        if len(matches)!=1:raise UpdateError('The update checksum is missing or ambiguous.')
        return matches[0].lower()

    def _prepare_incremental(self,http,release):
        if (self.root/inc.INSTALLED).is_symlink():raise UpdateError('Invalid installed file inventory.')
        previous=inc.parse_manifest((self.root/inc.INSTALLED).read_bytes(),self.current)
        helper=inc.safe_path(self.root,'evora-updater.exe')
        helper_info=next(item for item in previous['files'] if item['path']=='evora-updater.exe')
        if inc.digest(helper)!=helper_info['sha256']:raise UpdateError('The update helper needs the full installer.')
        expected=self._checksum(http,release,inc.MANIFEST)
        data=read_remote(http,release['incremental'][inc.MANIFEST]['browser_download_url'],inc.MAX_MANIFEST)
        if hashlib.sha256(data).hexdigest()!=expected:raise UpdateError('Update manifest verification failed.')
        manifest=inc.parse_manifest(data,release['tag'].lstrip('v'))
        if manifest['bundle_size']!=release['incremental'][inc.BUNDLE]['size']:raise UpdateError('Update package size mismatch.')
        # A failed health check always leaves a full-installer route for this release.
        stage=self._stage(release['tag'])
        result=stage/'result.json'
        if result.exists() and json.loads(result.read_bytes()).get('success') is False:raise UpdateError('Use the full installer after rollback.')
        changed,deleted=inc.plan_files(self.root,previous,manifest)
        total=sum(item['compressed_size'] for item in {f['compressed_sha256']:f for f in changed}.values())
        if total>=release['asset']['size']:raise UpdateError('The full installer is smaller.')
        required=sum(f['size'] for f in changed)
        backups=sum(inc.safe_path(self.root,f['path']).stat().st_size for f in changed if f['before'] is not None)+sum(f['size'] for f in deleted)
        stage_space=required+total;root_space=required+backups
        if os.stat(stage).st_dev==os.stat(self.root).st_dev:stage_space+=root_space
        if shutil.disk_usage(stage).free<stage_space+64*1024**2 or shutil.disk_usage(self.root).free<root_space+64*1024**2:
            raise UpdateError('Not enough disk space to stage the update.')
        baseline=inc.digest(self.root/inc.INSTALLED)
        (stage/'manifest.json').write_bytes(data)
        return dict(stage=stage,expected=expected,baseline=baseline,manifest=manifest,changes=changed,deletes=deleted,total=total)

    def _fallback(self,message):
        self.incremental=None;self.expected=None
        asset=self.release['asset']
        self.set(status='available',mode='installer',file_count=0,downloaded_bytes=0,total_bytes=asset['size'],
            download_url=asset['browser_download_url'],error=message)

    def _download_incremental(self):
        package=self.incremental
        try:
            with client() as http:
                done=inc.stage_download(http,remote,package['stage'],package['changes'],
                    self.release['incremental'][inc.BUNDLE]['browser_download_url'],package['manifest']['bundle_size'],
                    self.stop,lambda count:self.set(downloaded_bytes=count))
            if not done:self.set(status='available');return
            self.expected=package['expected']
            self.set(status='ready',downloaded_bytes=package['total'],error=None)
        except inc.RangeUnavailable as error:self._fallback(str(error))
        except (ValueError,OSError,httpx.HTTPError,EOFError) as error:
            self.set(status='error',error=str(error) if isinstance(error,inc.IncrementalError) else 'Download interrupted. Retry to resume.')

    def _install_incremental(self):
        package=self.incremental;stage=package['stage']
        if inc.digest(self.root/inc.INSTALLED)!=package['baseline'] or inc.digest(stage/'manifest.json')!=package['expected']:
            raise UpdateError('Application files changed. Check for updates again.')
        previous=inc.parse_manifest((self.root/inc.INSTALLED).read_bytes(),self.current)
        changes,deletes=inc.plan_files(self.root,previous,package['manifest'])
        if changes!=package['changes'] or deletes!=package['deletes']:raise UpdateError('Application files changed. Check for updates again.')
        for item in changes:
            if inc.digest(inc.safe_path(stage/'payload',item['path']))!=item['sha256']:raise UpdateError('Update verification failed. Download again.')
        owner=getattr(self.app.state,'update_owner_pid',0);marker=getattr(self.app.state,'update_stop_marker','')
        if not owner or not marker:raise UpdateError('Restart EVORA from its desktop shortcut before updating.')
        helper=inc.safe_path(self.root,'evora-updater.exe')
        info=next(f for f in previous['files'] if f['path']=='evora-updater.exe')
        if inc.digest(helper)!=info['sha256']:raise UpdateError('Update helper verification failed.')
        bootstrap=stage/'bootstrap.exe'
        if bootstrap.is_symlink():raise UpdateError('Invalid update helper.')
        shutil.copyfile(helper,bootstrap)
        if inc.digest(bootstrap)!=info['sha256']:raise UpdateError('Update helper verification failed.')
        plan=dict(root=str(self.root),stage=str(stage),manifest_sha256=package['expected'],baseline_sha256=package['baseline'],
            changes=changes,deletes=deletes,owner_pid=owner,backend_pid=os.getpid(),stop_marker=marker,
            health_file=str(stage/'health.json'),result_file=str(stage/'result.json'))
        path=stage/'plan.json';path.write_text(json.dumps(plan),encoding='utf-8')
        self.installer=subprocess.Popen([str(bootstrap),'--plan',str(path)],close_fds=True)
        self.helper_process=True
        self.set(status='installing',error=None)
        return self.status()

    def download(self):
        with self.lock:
            if not self.can_install:raise AccessError(400,'MANUAL_UPDATE','Use the release download for this installation.')
            if self.state['status'] in ('checking','downloading','installing'):return self.status()
            if not self.release or not self.release['newer'] or not self.release['asset'] or not self.release['checksum']:
                raise AccessError(409,'UPDATE_UNAVAILABLE','Check for an update with a published checksum first.')
            self.stop.clear();self.state.update(status='downloading',error=None)
            threading.Thread(target=self._download,daemon=True).start()
            return self.status()

    def _download(self):
        if self.incremental:return self._download_incremental()
        try:
            target,partial=self._paths();release=self.release;size=release['asset']['size']
            with client() as http:
                manifest=read_remote(http,release['checksum']['browser_download_url'],65536).decode('ascii')
                matches=re.findall(r'^([a-fA-F0-9]{64})[ \t]+\*?'+re.escape(INSTALLER)+r'\r?$',manifest,re.MULTILINE)
                if len(matches)!=1:raise UpdateError('The installer checksum is missing or ambiguous.')
                expected=matches[0].lower()
                if target.exists() and target.stat().st_size==size and sha256(target)==expected:
                    self.expected=expected;self.set(status='ready',downloaded_bytes=size);return
                offset=partial.stat().st_size if partial.exists() else 0
                if offset>size:partial.unlink();offset=0
                self.set(downloaded_bytes=offset)
                if offset<size:
                    with remote(http,release['asset']['browser_download_url'],{'Range':f'bytes={offset}-'} if offset else {}) as response:
                        if response.status_code==206:
                            match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                            if not match or int(match[1])!=offset or int(match[3])!=size:raise UpdateError('The resumed download range is invalid.')
                        elif response.status_code==200:offset=0
                        else:raise UpdateError('The installer download could not start.')
                        with os.fdopen(os.open(partial,os.O_WRONLY|os.O_CREAT|(os.O_APPEND if offset else os.O_TRUNC),0o600),'ab' if offset else 'wb') as output:
                            if os.name=='nt':
                                from backend.windows_credentials import secure_path
                                secure_path(partial)
                            started=time.monotonic()
                            for chunk in response.iter_bytes():
                                if time.monotonic()-started>7200:raise UpdateError('Download timed out. Retry to resume.')
                                if self.stop.is_set():self.set(status='available');return
                                offset+=len(chunk)
                                if offset>size:raise UpdateError('The installer download exceeded its expected size.')
                                output.write(chunk);self.set(downloaded_bytes=offset)
                            output.flush();os.fsync(output.fileno())
                if partial.stat().st_size!=size:raise UpdateError('The download is incomplete. Retry to resume.')
                if sha256(partial)!=expected:
                    partial.unlink();raise UpdateError('Installer verification failed. Download the update again.')
                os.replace(partial,target);self.expected=expected
                self.set(status='ready',downloaded_bytes=size,error=None)
        except UpdateError as error:self.set(status='error',error=str(error))
        except (httpx.HTTPError,ValueError,OSError,TypeError):self.set(status='error',error='Download interrupted. Retry to resume.')

    def install(self):
        with self.lock:
            if not self.can_install or self.state['status']!='ready' or not self.expected:
                raise AccessError(409,'UPDATE_NOT_READY','Download and verify the update first.')
            self.set(status='installing',error=None)
            try:return self._install_ready()
            except Exception:
                if self.state['status']=='installing':self.set(status='ready')
                raise

    def _install_ready(self):
        with self.app.state.database.connect() as connection:
            busy=sum(connection.execute(f"SELECT count(*) FROM {table} WHERE status IN ('queued','running')").fetchone()[0]
                for table in ('processing_runs','analysis_runs'))
        if busy:raise AccessError(409,'PROCESSING_ACTIVE','Wait for processing and analysis to finish before installing.')
        if self.incremental:
            try:return self._install_incremental()
            except (ValueError,OSError,KeyError) as error:
                self._fallback(str(error))
                raise AccessError(409,'UPDATE_VERIFICATION_FAILED',str(error)) from None
        target,_=self._paths()
        if not target.is_file() or sha256(target)!=self.expected:
            self.set(status='error',error='Installer verification failed. Download the update again.')
            raise AccessError(409,'UPDATE_VERIFICATION_FAILED','Installer verification failed. Download the update again.')
        args=[str(target),'/NORESTART','/CLOSEAPPLICATIONS']
        installed=Path(sys.executable).resolve().parent.parent
        if (installed/'EVORA.exe').is_file() and Path(sys.executable).parent.name.lower()=='backend':args.append('/DIR='+str(installed))
        try:self.installer=subprocess.Popen(args,close_fds=True)
        except OSError:raise AccessError(500,'INSTALLER_UNAVAILABLE','Could not open the update installer.') from None
        self.set(status='installing',error=None)
        return self.status()


class CheckRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    automatic: bool=False


def administrator(request:Request):
    actor=authenticated_actor(request)
    if request.app.state.local_auth:admin(actor)
    return actor


@router.get('/health',operation_id='getUpdateHealth')
def health():return {'version':APP_VERSION}


@router.get('',operation_id='getUpdateStatus',dependencies=[Depends(authenticated_actor)])
def get_status(request:Request):
    request.app.state.load_settings()
    return request.app.state.updates.status()


@router.post('/check',operation_id='checkForUpdates',dependencies=[Depends(administrator),Depends(csrf)])
def check(body:CheckRequest,request:Request):
    request.app.state.load_settings()
    return request.app.state.updates.check(body.automatic)


@router.post('/download',operation_id='downloadUpdate',dependencies=[Depends(administrator),Depends(csrf)])
def download(request:Request):return request.app.state.updates.download()


@router.post('/cancel',operation_id='cancelUpdateDownload',dependencies=[Depends(administrator),Depends(csrf)])
def cancel(request:Request):
    request.app.state.updates.stop.set()
    return request.app.state.updates.status()


@router.post('/install',operation_id='installUpdate',dependencies=[Depends(administrator),Depends(csrf)])
async def install(request:Request):return await run_in_threadpool(request.app.state.updates.install)
