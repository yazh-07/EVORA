"""Offline workstation identities, opaque sessions, recovery and administration."""
import hashlib
import secrets
import sqlite3
import time
from typing import Annotated, Literal
from uuid import UUID, uuid4

from sqlcipher3 import dbapi2 as encrypted_sqlite
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.auth import Actor, authenticated_actor, require_case_access, CaseAccessGrant
from backend.errors import AccessError

COOKIE = 'evora_session'
IDLE_SECONDS = 30 * 60
ABSOLUTE_SECONDS = 12 * 60 * 60
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)
# Equal-cost verification for unknown usernames; never log submitted secrets.
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))
router = APIRouter(prefix='/api/v1')



def initialize_auth(db):
    with db.connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS local_users (
          id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('administrator','investigator','reviewer')),
          disabled INTEGER NOT NULL DEFAULT 0, must_change_password INTEGER NOT NULL DEFAULT 0,
          recovery_hash TEXT, created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS local_sessions (
          digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES local_users(id),
          created_at REAL NOT NULL, last_seen REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS auth_attempts (bucket TEXT NOT NULL, attempted_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS auth_attempts_bucket ON auth_attempts(bucket,attempted_at);
        CREATE TABLE IF NOT EXISTS account_audit (
          id TEXT PRIMARY KEY, actor_id TEXT, action TEXT NOT NULL, target_id TEXT, created_at REAL NOT NULL);
        CREATE TRIGGER IF NOT EXISTS account_audit_no_update BEFORE UPDATE ON account_audit
          BEGIN SELECT RAISE(ABORT,'Immutable account audit'); END;
        CREATE TRIGGER IF NOT EXISTS account_audit_no_delete BEFORE DELETE ON account_audit
          BEGIN SELECT RAISE(ABORT,'Immutable account audit'); END;
        CREATE TRIGGER IF NOT EXISTS account_audit_no_replace BEFORE INSERT ON account_audit
          WHEN EXISTS(SELECT 1 FROM account_audit WHERE id=NEW.id OR rowid=NEW.rowid)
          BEGIN SELECT RAISE(ABORT,'Immutable account audit'); END;
        ''')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def audit(c, actor, action, target=None):
    c.execute('INSERT INTO account_audit VALUES (?,?,?,?,?)', (str(uuid4()), actor, action, target, time.time()))


def verify(encoded, password):
    try:
        return HASHER.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def wire(row):
    return {key: row[key] for key in ('id', 'username', 'display_name', 'role')} | {
        'disabled': bool(row['disabled']), 'must_change_password': bool(row['must_change_password'])}


def require_local(request):
    if not request.app.state.local_auth:
        raise AccessError(404, 'NOT_FOUND', 'Local accounts are unavailable in the explicit test adapter.')


def csrf(request: Request):
    require_local(request)
    origin = request.headers.get('origin')
    expected = str(request.base_url).rstrip('/')
    if (request.headers.get('x-evora-request') != '1' or
            (origin is not None and origin != expected) or request.headers.get('sec-fetch-site') == 'cross-site'):
        raise AccessError(403, 'INVALID_ORIGIN', 'Open EVORA directly on this workstation and retry.')


def throttle(request, username):
    # Commit the attempt before credential verification; failed authentication also counts.
    host = request.client.host if request.client else 'local'
    buckets = [('host:' + digest(host), 30), ('account:' + digest(username.casefold()), 8)]
    now = time.time()
    if request.app.state.database.locked:
        # The encrypted throttle table cannot be read before a valid password.
        with request.app.state.unlock_throttle_lock:
            attempts = request.app.state.unlock_attempts
            for bucket, maximum in buckets:
                attempts[bucket] = [stamp for stamp in attempts[bucket] if stamp > now - 300]
                if len(attempts[bucket]) >= maximum:
                    raise AccessError(429, 'TRY_LATER', 'Too many attempts. Wait five minutes before trying again.')
            for bucket, _ in buckets:
                attempts[bucket].append(now)
        return
    with request.app.state.database.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM auth_attempts WHERE attempted_at<?', (now - 300,))
        for bucket, maximum in buckets:
            if c.execute('SELECT count(*) FROM auth_attempts WHERE bucket=?', (bucket,)).fetchone()[0] >= maximum:
                raise AccessError(429, 'TRY_LATER', 'Too many attempts. Wait five minutes before trying again.')
        c.executemany('INSERT INTO auth_attempts VALUES (?,?)', [(bucket, now) for bucket, _ in buckets])


def issue(c, request, response, user):
    c.execute('DELETE FROM local_sessions WHERE created_at<? OR last_seen<?', (time.time()-ABSOLUTE_SECONDS, time.time()-IDLE_SECONDS))
    old = request.cookies.get(COOKIE)
    if old:
        c.execute('DELETE FROM local_sessions WHERE digest=?', (digest(old),))
    token = secrets.token_urlsafe(32)
    c.execute('INSERT INTO local_sessions VALUES (?,?,?,?)', (digest(token), user['id'], time.time(), time.time()))
    response.set_cookie(COOKIE, token, httponly=True, samesite='strict', secure=request.url.scheme == 'https', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return wire(user)


def session_actor(request):
    if request.app.state.database.locked:
        return None
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 200:
        return None
    now = time.time()
    with request.app.state.database.connect() as c:
        row = c.execute('SELECT u.*,s.created_at AS session_created,s.last_seen FROM local_sessions s JOIN local_users u ON u.id=s.user_id WHERE s.digest=?', (digest(token),)).fetchone()
        if row is None or row['disabled'] or now-row['session_created'] >= ABSOLUTE_SECONDS or now-row['last_seen'] >= IDLE_SECONDS:
            c.execute('DELETE FROM local_sessions WHERE digest=?', (digest(token),))
            return None
        if request.url.path == '/api/v1/auth/activity':
            c.execute('UPDATE local_sessions SET last_seen=? WHERE digest=?', (now, digest(token)))
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        csrf(request)
        if row['role'] == 'reviewer' and request.url.path not in ('/api/v1/auth/logout', '/api/v1/auth/password', '/api/v1/auth/activity'):
            raise AccessError(403, 'READ_ONLY', 'This account has read-only access.')
    if row['must_change_password'] and request.url.path not in ('/api/v1/auth/me', '/api/v1/auth/logout', '/api/v1/auth/password', '/api/v1/auth/activity'):
        raise AccessError(403, 'PASSWORD_CHANGE_REQUIRED', 'Change your temporary password before opening cases.')
    return Actor(row['id'], role=row['role'])


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Credentials(Input):
    username: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')
    password: str = Field(min_length=1, max_length=256)


class NewAccount(Credentials):
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)


class CreateUser(NewAccount):
    role: Literal['administrator','investigator','reviewer'] = 'investigator'


class PasswordChange(Input):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class Recovery(Input):
    username: str = Field(min_length=1, max_length=64)
    recovery_code: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=256)


class UserUpdate(Input):
    role: Literal['administrator','investigator','reviewer'] | None = None
    disabled: bool | None = None
    new_password: str | None = Field(default=None, min_length=12, max_length=256)


def admin(actor):
    if actor.role != 'administrator':
        raise AccessError(403, 'ADMIN_REQUIRED', 'Administrator access required.')


@router.get('/auth/status')
def status(request: Request, response: Response):
    require_local(request)
    response.headers['Cache-Control'] = 'no-store'
    database = request.app.state.database
    if database.locked:
        needed = False
    else:
        with database.connect() as c:
            needed = c.execute('SELECT 1 FROM local_users LIMIT 1').fetchone() is None
    return dict(setup_required=needed, offline_mode=request.app.state.offline_mode, database_encrypted=database.encrypted, database_locked=database.locked)


@router.post('/auth/setup', dependencies=[Depends(csrf)])
def setup(body: NewAccount, request: Request, response: Response):
    if request.app.state.database.locked:
        raise AccessError(409, 'ALREADY_CONFIGURED', 'An administrator already exists. Sign in instead.')
    throttle(request, body.username)
    encoded, recovery = HASHER.hash(body.password), secrets.token_urlsafe(32)
    uid = str(uuid4())
    with request.app.state.database.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM local_users LIMIT 1').fetchone():
            raise AccessError(409, 'ALREADY_CONFIGURED', 'An administrator already exists. Sign in instead.')
        c.execute('INSERT INTO local_users VALUES (?,?,?,?,?,0,0,?,?)', (uid, body.username, body.display_name, encoded, 'administrator', digest(recovery), time.time()))
        audit(c, uid, 'setupAdministrator', uid)
        user = c.execute('SELECT * FROM local_users WHERE id=?', (uid,)).fetchone()
        result = dict(user=issue(c, request, response, user), recovery_code=recovery)
    protect_database(request, body.username, body.password, recovery)
    return result


def protect_database(request, username, password, recovery):
    try:
        request.app.state.database.enable(username, password, recovery)
    except Exception:
        raise AccessError(500, 'ENCRYPTION_FAILED', 'Database encryption could not complete. Your original data is preserved. Check local storage permissions and retry signing in.') from None


def unlock_database(request, background, username, secret, *, recovery=False):
    database = request.app.state.database
    unlocked = database.unlock(username, secret, recovery=recovery)
    if not request.app.state.database_ready:
        request.app.state.initialize_database()
    if unlocked:
        from backend.analysis import recover_analysis_runs
        background.add_task(recover_analysis_runs, request.app)


@router.post('/auth/login', dependencies=[Depends(csrf)])
def login(body: Credentials, request: Request, response: Response, background: BackgroundTasks):
    throttle(request, body.username)
    unlock_database(request, background, body.username, body.password)
    database = request.app.state.database
    with database.guard():
        with database.connect() as c:
            user = c.execute('SELECT * FROM local_users WHERE username=? COLLATE NOCASE', (body.username,)).fetchone()
            valid = verify(user['password_hash'] if user else DUMMY_HASH, body.password)
            if not valid or user['disabled']:
                raise AccessError(401, 'INVALID_LOGIN', 'Username or password is incorrect.')
        migrating = database.protect and not database.encrypted and user['role'] == 'administrator'
        # Existing recovery hashes cannot wrap a key; migration supplies a replacement.
        replacement = secrets.token_urlsafe(32) if migrating else None
        with database.credentials(user['username'], body.password):
            with database.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                if replacement:
                    c.execute('UPDATE local_users SET recovery_hash=? WHERE id=?', (digest(replacement), user['id']))
                audit(c, user['id'], 'login', user['id'])
                result = dict(user=issue(c, request, response, user))
        if migrating:
            protect_database(request, user['username'], body.password, replacement)
            result['recovery_code'] = replacement
        return result


@router.get('/auth/me')
def me(request: Request, response: Response, actor: Annotated[Actor, Depends(authenticated_actor)]):
    response.headers['Cache-Control'] = 'no-store'
    with request.app.state.database.connect() as c:
        user = c.execute('SELECT * FROM local_users WHERE id=?', (actor.id,)).fetchone()
        if user is None:
            raise AccessError(401, 'UNAUTHORIZED', 'Sign in to a local account.')
        return dict(user=wire(user), offline_mode=request.app.state.offline_mode)


@router.post('/auth/logout', dependencies=[Depends(csrf)])
def logout(request: Request, response: Response):
    if request.app.state.database.locked:
        response.delete_cookie(COOKIE, path='/')
        return dict(ok=True)
    with request.app.state.database.connect() as c:
        token = request.cookies.get(COOKIE, '')
        row = c.execute('SELECT user_id FROM local_sessions WHERE digest=?', (digest(token),)).fetchone()
        c.execute('DELETE FROM local_sessions WHERE digest=?', (digest(token),))
        if row:
            audit(c, row['user_id'], 'logout', row['user_id'])
    response.delete_cookie(COOKIE, path='/')
    return dict(ok=True)


@router.post('/auth/password')
def password(body: PasswordChange, request: Request, response: Response, actor: Annotated[Actor, Depends(authenticated_actor)]):
    throttle(request, actor.id)
    database = request.app.state.database
    with database.guard():
        with database.connect() as c:
            user = c.execute('SELECT * FROM local_users WHERE id=?', (actor.id,)).fetchone()
            if not verify(user['password_hash'], body.current_password):
                raise AccessError(400, 'INVALID_PASSWORD', 'Current password is incorrect.')
        with database.credentials(user['username'], body.new_password):
            with database.connect() as c:
                c.execute('UPDATE local_users SET password_hash=?,must_change_password=0 WHERE id=?', (HASHER.hash(body.new_password), actor.id))
                c.execute('DELETE FROM local_sessions WHERE user_id=?', (actor.id,))
                audit(c, actor.id, 'changePassword', actor.id)
                return dict(user=issue(c, request, response, c.execute('SELECT * FROM local_users WHERE id=?', (actor.id,)).fetchone()))


@router.post('/auth/recover', dependencies=[Depends(csrf)])
def recover(body: Recovery, request: Request, background: BackgroundTasks):
    throttle(request, body.username)
    unlock_database(request, background, body.username, body.recovery_code, recovery=True)
    database = request.app.state.database
    with database.guard():
        with database.connect() as c:
            user = c.execute('SELECT * FROM local_users WHERE username=? COLLATE NOCASE', (body.username,)).fetchone()
            if not user or user['disabled'] or not user['recovery_hash'] or not secrets.compare_digest(user['recovery_hash'], digest(body.recovery_code)):
                raise AccessError(400, 'INVALID_RECOVERY', 'Username or recovery code is incorrect.')
        replacement = secrets.token_urlsafe(32)
        with database.credentials(user['username'], body.new_password, replacement):
            with database.connect() as c:
                c.execute('UPDATE local_users SET password_hash=?,must_change_password=0,recovery_hash=? WHERE id=?', (HASHER.hash(body.new_password), digest(replacement), user['id']))
                c.execute('DELETE FROM local_sessions WHERE user_id=?', (user['id'],))
                audit(c, user['id'], 'recoverAccount', user['id'])
        protect_database(request, user['username'], body.new_password, replacement)
    return dict(recovery_code=replacement)


@router.get('/accounts')
def users(request: Request, actor: Annotated[Actor, Depends(authenticated_actor)]):
    admin(actor)
    with request.app.state.database.connect() as c:
        return dict(items=[wire(row) for row in c.execute('SELECT * FROM local_users ORDER BY username')])


@router.post('/accounts', status_code=201)
def create_user(body: CreateUser, request: Request, actor: Annotated[Actor, Depends(authenticated_actor)]):
    admin(actor)
    encoded, uid = HASHER.hash(body.password), str(uuid4())
    with request.app.state.database.credentials(body.username, body.password):
        with request.app.state.database.connect() as c:
            try:
                c.execute('INSERT INTO local_users VALUES (?,?,?,?,?,0,1,NULL,?)', (uid, body.username, body.display_name, encoded, body.role, time.time()))
            except (sqlite3.IntegrityError, encrypted_sqlite.IntegrityError):
                raise AccessError(409, 'USERNAME_EXISTS', 'That username is already in use.') from None
            audit(c, actor.id, 'createAccount', uid)
            return dict(user=wire(c.execute('SELECT * FROM local_users WHERE id=?', (uid,)).fetchone()))


@router.put('/accounts/{userId}')
def update_user(userId: UUID, body: UserUpdate, request: Request, actor: Annotated[Actor, Depends(authenticated_actor)]):
    admin(actor)
    uid = str(userId)
    encoded = HASHER.hash(body.new_password) if body.new_password else None
    database = request.app.state.database
    with database.guard():
        with database.connect() as c:
            current = c.execute('SELECT username FROM local_users WHERE id=?', (uid,)).fetchone()
            if current is None:
                raise AccessError(404, 'NOT_FOUND', 'Account not found.')
        with database.credentials(current['username'], body.new_password):
            with request.app.state.database.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                user = c.execute('SELECT * FROM local_users WHERE id=?', (uid,)).fetchone()
                if not user:
                    raise AccessError(404, 'NOT_FOUND', 'Account not found.')
                role = body.role or user['role']
                disabled = body.disabled if body.disabled is not None else bool(user['disabled'])
                if user['role'] == 'administrator' and not user['disabled'] and (role != 'administrator' or disabled):
                    if c.execute("SELECT count(*) FROM local_users WHERE role='administrator' AND disabled=0").fetchone()[0] <= 1:
                        raise AccessError(409, 'LAST_ADMIN', 'Keep at least one active administrator.')
                c.execute('UPDATE local_users SET role=?,disabled=? WHERE id=?', (role, disabled, uid))
                if encoded:
                    c.execute('UPDATE local_users SET password_hash=?,must_change_password=1 WHERE id=?', (encoded, uid))
                c.execute('DELETE FROM local_sessions WHERE user_id=?', (uid,))
                audit(c, actor.id, 'updateAccount', uid)
                return dict(user=wire(c.execute('SELECT * FROM local_users WHERE id=?', (uid,)).fetchone()))


class Membership(Input):
    user_id: UUID = Field(strict=False)
    grant: bool = True


@router.get('/cases/{caseId}/members')
def members(request: Request, grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
    admin(grant.actor)
    with request.app.state.database.connect() as c:
        return dict(items=[dict(row) for row in c.execute('SELECT u.id,u.username,u.display_name,u.role FROM local_users u JOIN case_members m ON m.actor_id=u.id WHERE m.case_id=?', (str(grant.case_id),))])


@router.put('/cases/{caseId}/members')
def membership(body: Membership, request: Request, grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
    admin(grant.actor)
    with request.app.state.database.connect() as c:
        if not c.execute('SELECT 1 FROM local_users WHERE id=?', (str(body.user_id),)).fetchone():
            raise AccessError(404, 'NOT_FOUND', 'Account not found.')
        if body.grant:
            c.execute('INSERT OR IGNORE INTO case_members VALUES (?,?)', (str(grant.case_id), str(body.user_id)))
        else:
            c.execute('DELETE FROM case_members WHERE case_id=? AND actor_id=?', (str(grant.case_id), str(body.user_id)))
        audit(c, grant.actor.id, 'grantCaseAccess' if body.grant else 'revokeCaseAccess', str(body.user_id))
    return dict(ok=True)

@router.get('/accounts/audit')
def account_history(request: Request, actor: Annotated[Actor, Depends(authenticated_actor)]):
    admin(actor)
    with request.app.state.database.connect() as c:
        return dict(items=[dict(row) for row in c.execute('SELECT * FROM account_audit ORDER BY created_at DESC,id DESC LIMIT 100')])

@router.post('/auth/activity')
def activity(actor: Annotated[Actor, Depends(authenticated_actor)]):
    return dict(ok=True)
