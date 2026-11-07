// Real legacy migration, encrypted storage and cold-start password unlock through the UI.
import assert from 'node:assert/strict';
import {execFileSync,spawn} from 'node:child_process';
import {createServer} from 'node:net';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.EVORA_PLAYWRIGHT_MODULE??'playwright');
const root=fileURLToPath(new URL('../..',import.meta.url));
const scratch=await mkdtemp(join(tmpdir(),'evora-encryption-browser-'));
const database=join(scratch,'case.sqlite3'),python=process.env.EVORA_TEST_PYTHON??'python';
const probe=createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
const origin=`http://127.0.0.1:${port}`,password='synthetic migration passphrase';
execFileSync(python,['-c',`import sys,time
from backend.app import create_app
from backend.local_auth import HASHER,digest
app=create_app(sys.argv[1]);app.state.initialize_database()
with app.state.database.connect() as c:
 c.execute('INSERT INTO local_users VALUES (?,?,?,?,?,0,0,?,?)',('00000000-0000-4000-8000-000000000001','admin','Administrator',HASHER.hash(sys.argv[2]),'administrator',digest('legacy-recovery-code'),time.time()))
 c.execute('INSERT INTO cases VALUES (?,?,?,?)',('00000000-0000-4000-8000-000000000002','Preserved migration case',None,'2026-11-07T00:00:00Z'))
 c.execute('INSERT INTO case_members VALUES (?,?)',('00000000-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000001'))
`,database,password],{cwd:root});
assert.equal((await readFile(database)).subarray(0,16).toString(),'SQLite format 3\0');
let server,closed,browser,diagnostics='';
async function start(){
 server=spawn(python,['-m','backend.run','--database',database,'--storage',join(scratch,'evidence'),'--port',String(port)],{cwd:root,env:{...process.env,EVORA_QA_MODEL:''},stdio:['ignore','ignore','pipe']});
 closed=new Promise(r=>server.once('close',r));server.stderr.on('data',b=>diagnostics=(diagnostics+b).slice(-3000));
 for(let i=0;i<100;i++){try{if((await fetch(origin+'/api/v1/auth/status')).ok)return;}catch{}if(server.exitCode!==null)throw Error(diagnostics);await new Promise(r=>setTimeout(r,100));}throw Error('Server startup timeout');
}
async function stop(){if(server&&server.exitCode===null){server.kill('SIGTERM');await closed;}}
try{
 await start();browser=await chromium.launch({executablePath:process.env.EVORA_CHROME_PATH,headless:true,args:['--no-sandbox']});
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin);await page.getByLabel('Username',{exact:true}).fill('admin');await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await page.getByRole('heading',{name:'Save your recovery code',exact:true}).waitFor();
 const code=await page.locator('.recovery-code pre').innerText();assert.notEqual(code,'legacy-recovery-code');
 assert.notEqual((await readFile(database)).subarray(0,16).toString(),'SQLite format 3\0');
 const metadata=await readFile(database+'.keys.json','utf8');assert.ok(!metadata.includes(password));assert.ok(!metadata.includes(code));
 await page.getByRole('button',{name:'I saved the recovery code',exact:true}).click();await page.getByRole('button',{name:'Open case Preserved migration case',exact:true}).waitFor();
 await stop();await start();await page.reload();
 await page.getByText('Your account password also unlocks the encrypted database.',{exact:false}).waitFor();
 await page.getByLabel('Username',{exact:true}).fill('admin');await page.getByLabel('Password',{exact:true}).fill('incorrect migration password');await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('alert').waitFor();
 assert.equal((await (await fetch(origin+'/api/v1/auth/status')).json()).database_locked,true);
 await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('button',{name:'Open case Preserved migration case',exact:true}).waitFor();
 assert.equal((await (await fetch(origin+'/api/v1/auth/status')).json()).database_locked,false);
 assert.deepEqual(errors,[]);
 console.log('PASS database encryption browser: legacy case migration, replacement recovery-code display, encrypted file, wrapped secrets, cold-start lock, prior cookie rejection, wrong-password rejection and password unlock preserving cases.');
}finally{await browser?.close();await stop();await rm(scratch,{recursive:true,force:true});}
