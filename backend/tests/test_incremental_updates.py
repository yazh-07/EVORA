"""Real release packages and HTTP ranges; no installers or external services."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from backend import incremental as inc, updates
from backend.version import APP_VERSION
from scripts.build_incremental import build


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(TemporaryDirectory());self.base=Path(self.temp)
        self.root=self.base/'installed';self.next=self.base/'release';self.cache=self.base/'cache'
        for root in (self.root,self.next):
            (root/'backend/_internal').mkdir(parents=True)
            for name,data in {'EVORA.exe':b'desktop','evora-updater.exe':b'helper','icon.ico':b'icon',
                'backend/evora.exe':b'backend','backend/_internal/model.bin':b'large unchanged model'*5000,
                'backend/_internal/python314.dll':b'runtime','backend/_internal/ui.js':b'old UI'}.items():
                (root/name).write_bytes(data)
        (self.root/'backend/obsolete.txt').write_bytes(b'obsolete')
        (self.next/'backend/_internal/ui.js').write_bytes(b'improved UI')
        (self.next/'backend/new.txt').write_bytes(b'new file')
        self.old=self.package(self.root,self.base/'old',APP_VERSION)
        shutil.copyfile(self.base/'old'/inc.MANIFEST,self.root/inc.INSTALLED)
        # Match Inno Setup's duplicated runtime DLLs.
        shutil.copyfile(self.root/'backend/_internal/python314.dll',self.root/'backend/python314.dll')
        self.new=self.package(self.next,self.base/'new','9.0.0')
        self.manifest=(self.base/'new'/inc.MANIFEST).read_bytes();self.bundle=(self.base/'new'/inc.BUNDLE).read_bytes()
        self.data=self.base/'user-data';self.data.mkdir();(self.data/'cases.sqlite3').write_bytes(b'private evidence database')
        self.app=SimpleNamespace(state=SimpleNamespace(automatic_update_checks=True,update_owner_pid=123,
            update_stop_marker=str(self.data/'stop-123.update')))
        self.service=updates.Updates(self.app,can_install=True,installed_root=self.root,cache=self.cache)
        self.url=updates.REPOSITORY+'/releases/download/v9.0.0/'
        self.release={'tag_name':'v9.0.0','assets':[dict(name=name,size=size,browser_download_url=self.url+name) for name,size in
            [(inc.MANIFEST,len(self.manifest)),(inc.BUNDLE,len(self.bundle)),('SHA256SUMS',300),(updates.INSTALLER,1000000)]]}
        self.requests=[];self.ranges=True;self.corrupt=False;self.bad_manifest=False
        def response(request):
            self.requests.append(request)
            name=str(request.url).rsplit('/',1)[-1]
            if str(request.url)==updates.LATEST:return httpx.Response(200,json=self.release)
            if name=='SHA256SUMS':return httpx.Response(200,text=hashlib.sha256(self.manifest).hexdigest()+'  '+inc.MANIFEST+'\n')
            if name==inc.MANIFEST:return httpx.Response(200,content=b'{}' if self.bad_manifest else self.manifest)
            if name==inc.BUNDLE:
                if not self.ranges:return httpx.Response(200,content=self.bundle)
                start,end=map(int,request.headers['Range'][6:].split('-'))
                content=self.bundle[start:end+1]
                if self.corrupt:content=b'X'*len(content)
                return httpx.Response(206,content=content,headers={'Content-Range':f'bytes {start}-{end}/{len(self.bundle)}'})
            raise AssertionError('Unexpected network request: '+str(request.url))
        real=httpx.Client
        self.enterContext(patch.object(updates,'client',side_effect=lambda:real(transport=httpx.MockTransport(response))))

    def package(self,root,out,version):
        return build(root/'backend',root/'EVORA.exe',root/'evora-updater.exe',root/'icon.ico',out,version)

    def checked(self):
        self.service._check()
        self.assertEqual(self.service.state['status'],'available',self.service.state)
        self.assertEqual(self.service.state['mode'],'incremental',self.service.state)
        return self.service.incremental

    def test_completed_cache_is_pruned_without_touching_user_data_or_pending_updates(self):
        self.cache.mkdir();old=self.cache/('v'+APP_VERSION+'-incremental');old.mkdir();(old/'manifest.json').write_text('{}')
        unknown=self.cache/'my-data';unknown.mkdir();(unknown/'keep.txt').write_text('keep')
        future=self.cache/'v9.0.0-incremental';future.mkdir()
        journal=self.root/'.evora-update-journal';journal.mkdir()
        self.service._prune_cache();self.assertTrue(old.exists())
        journal.rmdir();self.service._prune_cache()
        self.assertFalse(old.exists());self.assertTrue(unknown.exists());self.assertTrue(future.exists())

    def test_downloads_only_changed_files_and_never_the_installer_or_models(self):
        package=self.checked();self.service._download()
        self.assertEqual(self.service.state['status'],'ready',self.service.state)
        changed={f['path'] for f in package['changes']}
        self.assertEqual(changed,{'backend/_internal/ui.js','backend/new.txt'})
        requested=[r for r in self.requests if r.url.path.endswith(inc.BUNDLE)]
        self.assertEqual(len(requested),2)
        expected={f"bytes={f['offset']}-{f['offset']+f['compressed_size']-1}" for f in package['changes']}
        self.assertEqual({r.headers['Range'] for r in requested},expected)
        self.assertFalse(any(r.url.path.endswith(updates.INSTALLER) for r in self.requests))
        self.assertEqual((self.data/'cases.sqlite3').read_bytes(),b'private evidence database')
        self.assertEqual(self.service.state['downloaded_bytes'],self.service.state['total_bytes'])
        self.assertLess(self.service.state['total_bytes'],len(self.bundle))

    def test_resumes_a_partial_segment_and_reuses_verified_staging(self):
        package=self.checked();item=package['changes'][0];objects=package['stage']/'objects';objects.mkdir()
        blob=self.bundle[item['offset']:item['offset']+item['compressed_size']]
        (objects/(item['compressed_sha256']+'.gz')).write_bytes(blob[:7])
        self.service._download()
        self.assertEqual(self.service.state['status'],'ready',self.service.state)
        self.assertIn(f"bytes={item['offset']+7}-{item['offset']+item['compressed_size']-1}",[r.headers.get('Range') for r in self.requests])
        count=len(self.requests);self.service._download();self.assertEqual(len(self.requests),count)

    def test_range_unavailable_offers_installer_without_silently_downloading_it(self):
        self.checked();self.ranges=False;self.service._download()
        self.assertEqual(self.service.state['mode'],'installer');self.assertEqual(self.service.state['status'],'available')
        self.assertIn('full installer',self.service.state['error'])
        self.assertFalse(any(r.url.path.endswith(updates.INSTALLER) for r in self.requests))

    def test_corrupt_segments_and_tampered_manifest_never_become_ready(self):
        self.checked();self.corrupt=True;self.service._download()
        self.assertEqual(self.service.state['status'],'error');self.assertIsNone(self.service.expected)
        self.bad_manifest=True;self.service._check();self.assertEqual(self.service.state['mode'],'installer')

    def test_old_installations_and_failed_health_checks_use_full_installer(self):
        self.checked();stage=self.service.incremental['stage'];(stage/'result.json').write_text('{"success":false}')
        self.service._check();self.assertEqual(self.service.state['mode'],'installer')
        (stage/'result.json').unlink();(self.root/'evora-updater.exe').unlink()
        self.service._check();self.assertEqual(self.service.state['mode'],'installer')

    def test_unmanaged_collisions_and_modified_deletions_use_full_installer(self):
        (self.root/'backend/new.txt').write_bytes(b'local unmanaged')
        self.service._check();self.assertEqual(self.service.state['mode'],'installer')
        (self.root/'backend/new.txt').unlink();(self.root/'backend/obsolete.txt').write_bytes(b'local edit')
        self.service._check();self.assertEqual(self.service.state['mode'],'installer')

    def test_install_starts_private_helper_with_exact_verified_plan(self):
        package=self.checked();self.service._download()
        process=SimpleNamespace(poll=lambda:None)
        with patch.object(updates.subprocess,'Popen',return_value=process) as execute:
            self.service._install_incremental()
        args=execute.call_args.args[0];self.assertEqual(args[1],'--plan')
        plan=json.loads(Path(args[2]).read_text())
        self.assertEqual(Path(plan['root']),self.root.resolve());self.assertEqual(plan['changes'],package['changes'])
        self.assertEqual(plan['deletes'][0]['path'],'backend/obsolete.txt')
        self.assertEqual(plan['baseline_sha256'],inc.digest(self.root/inc.INSTALLED))
        self.assertEqual(Path(args[0]).read_bytes(),b'helper')
        # Installing has not modified the running application.
        self.assertEqual((self.root/'backend/_internal/ui.js').read_bytes(),b'old UI')

    def test_install_rejects_payload_changes_after_download(self):
        package=self.checked();self.service._download()
        item=package['changes'][0];inc.safe_path(package['stage']/'payload',item['path']).write_bytes(b'tampered')
        with patch.object(updates.subprocess,'Popen') as execute,self.assertRaises(updates.UpdateError):self.service._install_incremental()
        execute.assert_not_called()

    def test_path_validation_blocks_traversal_case_collisions_user_data_and_links(self):
        for name in ('../EVORA.exe','backend/../data','backend/vault/proof','backend/cases.sqlite3','backend/a:stream',
            'backend/NUL.txt','backend/a.','/EVORA.exe','backend//x','backend\\x'):
            with self.subTest(name=name),self.assertRaises(inc.IncrementalError):inc.safe_name(name)
        manifest=json.loads(self.manifest);manifest['files'].append({**manifest['files'][0],'path':manifest['files'][0]['path'].upper()})
        with self.assertRaises(inc.IncrementalError):inc.parse_manifest(json.dumps(manifest).encode())
        link=self.root/'backend/link'
        try:link.symlink_to(self.data,target_is_directory=True)
        except (OSError,NotImplementedError):return
        with self.assertRaises(inc.IncrementalError):inc.safe_path(self.root,'backend/link/file.txt')

    def test_decompression_is_bounded_by_declared_file_size(self):
        package=self.checked();item=package['changes'][0].copy();blob=gzip.compress(b'X'*10000)
        item.update(size=1,offset=0,compressed_size=len(blob),compressed_sha256=hashlib.sha256(blob).hexdigest())
        self.bundle=blob
        with updates.client() as http,self.assertRaises(inc.IncrementalError):
            inc.stage_download(http,updates.remote,package['stage'],[item],self.url+inc.BUNDLE,len(blob),threading.Event(),lambda n:None)
        self.assertFalse(inc.safe_path(package['stage']/'payload',item['path']).exists())
