"""App factory, SQLite startup and F01 case operations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import asyncio
import os
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.analysis import initialize_analysis, recover_analysis_runs, router as analysis_router
from backend.auth import CaseAccess, RejectTokens, TokenVerifier, authenticated_actor
from backend.audit import initialize_audit, router as audit_router
from backend.database import SQLiteDatabase
from backend.cases import SQLiteCaseAccess, initialize_cases, router
from backend.evidence import initialize_evidence, router as evidence_router
from backend.processing import initialize_processing, router as processing_router
from backend.observations import router as observations_router
from backend.entities import router as entities_router
from backend.events import router as events_router
from backend.findings import router as findings_router
from backend.reviews import initialize_reviews, router as reviews_router
from backend.overrides import initialize_overrides, router as overrides_router
from backend.triage_endpoints import router as triage_router
from backend.questions import router as questions_router
from backend.transcripts import initialize_transcripts, router as transcripts_router
from backend.image_understanding import router as image_understanding_router
from backend.video_understanding import router as video_understanding_router
from backend.chatgpt_connection import Connection, router as chatgpt_router
from starlette.concurrency import run_in_threadpool
from backend.local_auth import initialize_auth, router as local_auth_router
from backend.errors import AccessError, access_error, invalid_request


def validate_offline_endpoint(value):
    import ipaddress
    url = urlsplit(value)
    host = url.hostname
    try:
        local = host == 'localhost' or ipaddress.ip_address(host or '').is_loopback
    except ValueError:
        local = False
    if url.scheme not in ('http', 'https') or not local or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        raise AccessError(400, 'OFFLINE_ENDPOINT', 'Offline mode requires an Ollama endpoint on localhost or a loopback address.')


class OllamaEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    qa_url: str = "http://127.0.0.1:11434"

    @field_validator("qa_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        url = urlsplit(value)
        if (value != value.strip() or any(c.isspace() for c in value)
                or url.scheme not in {"http", "https"} or not url.hostname
                or url.username or url.password or url.path not in {"", "/"}
                or url.query or url.fragment):
            raise ValueError("Use an HTTP(S) origin without credentials.")
        _ = url.port  # Validate the port too.
        return value.rstrip("/")


class ProviderEndpoint(OllamaEndpoint):
    offline_mode: bool = True
    qa_provider: Literal['ollama', 'openai', 'chatgpt'] = 'ollama'
    openai_api_key: Optional[str] = Field(default=None, repr=False)
    openai_base_url: str = 'https://api.openai.com/v1'

    @field_validator('openai_api_key')
    @classmethod
    def validate_api_key(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError('Use an API key without whitespace or control characters.')
        return value

    @field_validator('openai_base_url')
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        url = urlsplit(value)
        if (value != value.strip() or any(c.isspace() for c in value)
                or url.scheme not in {'http', 'https'} or not url.hostname
                or url.username or url.password or url.query or url.fragment):
            raise ValueError('Use an HTTP(S) base URL without credentials, query or fragment.')
        _ = url.port
        return value.rstrip('/')


class Settings(ProviderEndpoint):
    vision_use_qa_model: bool = False
    vision_model: str = Field(default='', max_length=200)
    qa_model: str = Field(default="deepseek-r1:8b", min_length=1, max_length=200)
    detection_threshold: float = Field(default=0.7, ge=0.1, le=1.0, allow_inf_nan=False)
    show_provenance_rays: bool = True

    @field_validator("qa_model", "vision_model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if (value and not value.strip()) or any(c.isspace() for c in value):
            raise ValueError("Use a model name without whitespace.")
        return value


def create_app(
    database_path: str | Path | None = None,
    *,
    token_verifier: TokenVerifier | None = None,
    case_access: CaseAccess | None = None,
    storage_dir: str | Path | None = None,
    offline_mode: bool | None = None,
) -> FastAPI:
    """Configure an isolated app; opening SQLite is deferred until startup."""
    configured_path = (
        database_path
        if database_path is not None
        else os.environ.get("EVORA_DATABASE_PATH", "storage/evora.sqlite3")
    )
    if not str(configured_path).strip() or str(configured_path) == ":memory:":
        raise ValueError("EVORA_DATABASE_PATH must name a SQLite file.")
    database = SQLiteDatabase(Path(configured_path))

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        initialize_cases(database)
        if _app.state.local_auth:
            initialize_auth(database)
        initialize_evidence(database)
        initialize_audit(database)
        initialize_processing(database)
        initialize_analysis(database)
        initialize_reviews(database)
        initialize_overrides(database)
        initialize_transcripts(database)
        try:
            await recover_analysis_runs(_app)
            yield
        finally:
            _app.state.chatgpt_connection.cancel()
            if _app.state.graph_database is not None:
                _app.state.graph_database.close()

    app = FastAPI(
        title="EVORA backend skeleton",
        version="0.3.0",
        lifespan=lifespan,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.local_auth = token_verifier is None
    app.state.chatgpt_connection = Connection(app,database.path)
    app.state.offline_mode = (app.state.local_auth if offline_mode is None else offline_mode)
    if app.state.local_auth:
        from starlette.middleware.trustedhost import TrustedHostMiddleware
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]'])
    @app.middleware('http')
    async def local_session_headers(request: Request, call_next):
        response = await call_next(request)
        if app.state.local_auth and request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
            if getattr(request.state, 'actor_id', None):
                response.headers['X-Evora-User'] = request.state.actor_id
        return response
    app.include_router(local_auth_router)
    app.state.qa_model = os.environ.get("EVORA_QA_MODEL", "deepseek-r1:8b")
    app.state.qa_url = os.environ.get("EVORA_QA_URL", "http://127.0.0.1:11434").rstrip("/")
    app.state.qa_provider = os.environ.get('EVORA_QA_PROVIDER', 'ollama')
    app.state.openai_api_key = os.environ.get('OPENAI_API_KEY') or None
    app.state.openai_base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
    if app.state.offline_mode:
        app.state.qa_provider = 'ollama'
        app.state.openai_api_key = None
        validate_offline_endpoint(app.state.qa_url)
    app.state.vision_model = os.environ.get('EVORA_VISION_MODEL', '')
    app.state.vision_use_qa_model = False
    app.state.detection_threshold = 0.7
    app.state.show_provenance_rays = True
    app.state.database = database
    app.state.processing_lock = asyncio.Lock()
    app.state.analysis_lock = asyncio.Lock()
    app.state.graph_database = None
    app.state.storage_dir = Path(storage_dir if storage_dir is not None else
                                 os.environ.get("EVORA_STORAGE_DIR", "storage/evidence")).resolve()
    app.state.token_verifier = token_verifier if token_verifier is not None else RejectTokens()
    app.state.case_access = case_access if case_access is not None else SQLiteCaseAccess(database)
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.add_exception_handler(AccessError, access_error)

    @app.get("/api/v1/settings", dependencies=[Depends(authenticated_actor)])
    async def get_settings(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return {**{key: getattr(app.state, key) for key in Settings.model_fields if key not in ('openai_api_key', 'offline_mode', 'vision_model', 'vision_use_qa_model')},
                'has_openai_key': bool(app.state.openai_api_key), **({'has_chatgpt_connection':app.state.chatgpt_connection.status()['sharing']} if app.state.local_auth or app.state.qa_provider=='chatgpt' else {}), **({'offline_mode': app.state.offline_mode, 'vision_model': app.state.vision_model,
                'vision_use_qa_model': app.state.vision_use_qa_model} if app.state.local_auth or app.state.vision_model or app.state.vision_use_qa_model else {})}

    @app.put("/api/v1/settings", dependencies=[Depends(authenticated_actor)])
    async def put_settings(body: Settings, response: Response, request: Request):
        if app.state.local_auth:
            from backend.local_auth import admin
            admin(authenticated_actor(request))
        offline = body.offline_mode if 'offline_mode' in body.model_fields_set else app.state.offline_mode
        provider = body.qa_provider if 'qa_provider' in body.model_fields_set else app.state.qa_provider
        qa_url = body.qa_url if 'qa_url' in body.model_fields_set else app.state.qa_url
        base = body.openai_base_url if 'openai_base_url' in body.model_fields_set else app.state.openai_base_url
        if offline:
            if provider != 'ollama' or body.openai_api_key:
                raise AccessError(400, 'OFFLINE_MODE', 'Offline mode supports local Ollama models only.')
            validate_offline_endpoint(qa_url)
        if base != app.state.openai_base_url and app.state.openai_api_key and not body.openai_api_key:
            raise AccessError(400, 'PROVIDER_KEY_REQUIRED', 'Re-enter the API key when changing the provider base URL.')
        if not offline and provider == 'openai':
            from backend.image_understanding import safe_endpoint
            safe_endpoint(base, 'openai')
        # Validation finishes before any mutation. Omitted values remain unchanged.
        for key, value in body.model_dump(exclude_unset=True).items():
            if key == 'openai_api_key' and not value:
                continue
            setattr(app.state, key, value)
        if 'offline_mode' in body.model_fields_set and offline:
            app.state.chatgpt_connection.cancel()
        return await get_settings(response)

    @app.post("/api/v1/settings/models", dependencies=[Depends(authenticated_actor)])
    async def list_models(body: ProviderEndpoint, response: Response, request: Request):
        response.headers["Cache-Control"] = "no-store"
        provider = body.qa_provider if 'qa_provider' in body.model_fields_set else app.state.qa_provider
        if app.state.local_auth and 'offline_mode' in body.model_fields_set:
            from backend.local_auth import admin
            admin(authenticated_actor(request))
        offline = body.offline_mode if 'offline_mode' in body.model_fields_set else app.state.offline_mode
        if offline:
            if provider != 'ollama':
                raise AccessError(400, 'OFFLINE_MODE', 'Cloud providers are disabled in offline mode.')
            validate_offline_endpoint(body.qa_url if 'qa_url' in body.model_fields_set else app.state.qa_url)
        if provider == 'chatgpt':
            try:return await run_in_threadpool(app.state.chatgpt_connection.models,True)
            except (ValueError,KeyError,httpx.HTTPError,OSError):
                raise AccessError(502,'CHATGPT_UNAVAILABLE','Connect ChatGPT and authorize plan usage, then retry fetching models. Account limits may apply.') from None
        if provider == 'openai':
            api_key = body.openai_api_key or app.state.openai_api_key
            if not api_key:
                raise AccessError(400, 'OPENAI_KEY_REQUIRED', 'Enter an API key before testing the connection.')
            base_url = (body.openai_base_url if 'openai_base_url' in body.model_fields_set
                        else app.state.openai_base_url)
            if base_url != app.state.openai_base_url and not body.openai_api_key:
                raise AccessError(400, 'PROVIDER_KEY_REQUIRED', 'Enter a key explicitly when testing another provider URL.')
            from backend.image_understanding import safe_endpoint
            safe_endpoint(base_url, 'openai')
            url, field, name = base_url + '/models', 'data', 'id'
        else:
            url = (body.qa_url if 'qa_url' in body.model_fields_set else app.state.qa_url) + '/api/tags'
            field, name = 'models', 'name'
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0), trust_env=False, follow_redirects=False) as client:
                if provider == 'openai':
                    result = await client.get(url, headers={'Authorization': f'Bearer {api_key}'})
                else:
                    result = await client.get(url)
                result.raise_for_status()
                payload = result.json()
            models = payload[field]
            if not isinstance(models, list) or any(
                not isinstance(item, dict) or not isinstance(item.get(name), str)
                or not item[name].strip() for item in models
            ):
                raise ValueError("Invalid model list")
            catalog = {"models": sorted({item[name] for item in models})}
            if provider == 'openai' and any(isinstance(item.get('architecture'), dict) and
                    isinstance(item['architecture'].get('input_modalities'), list) for item in models):
                catalog['vision_models'] = sorted({item[name] for item in models
                    if isinstance(item.get('architecture'), dict) and
                    isinstance(item['architecture'].get('input_modalities'), list) and
                    'image' in item['architecture']['input_modalities']})
            return catalog
        except httpx.HTTPStatusError as error:
            if provider == 'openai':
                messages = {401: 'The provider rejected the API key (HTTP 401). Check that it is a key for this provider.',
                    403: 'The provider denied access (HTTP 403). Check API key permissions and account access.',
                    404: 'The provider model-list URL was not found (HTTP 404). Check the base URL and API path.',
                    429: 'The provider rate-limited the request (HTTP 429). Wait and retry; check your account limits.'}
                raise AccessError(502, 'OPENAI_UNAVAILABLE', messages.get(error.response.status_code,
                    'The provider could not return its model list. Retry or check the provider service status.')) from None
            raise AccessError(502, 'OLLAMA_UNAVAILABLE', 'Could not connect to Ollama or read its models.') from None
        except httpx.TimeoutException:
            raise AccessError(502, 'OPENAI_UNAVAILABLE' if provider == 'openai' else 'OLLAMA_UNAVAILABLE',
                'The model-list request timed out. Check connectivity and retry.') from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            if provider == 'openai':
                raise AccessError(502, 'OPENAI_UNAVAILABLE',
                                  'Could not connect to the OpenAI-compatible provider or read its models. Check the API key and base URL.') from None
            raise AccessError(502, "OLLAMA_UNAVAILABLE", "Could not connect to Ollama or read its models.") from None

    app.include_router(router)
    app.include_router(evidence_router)
    app.include_router(image_understanding_router)
    app.include_router(video_understanding_router)
    app.include_router(chatgpt_router)
    app.include_router(audit_router)
    app.include_router(processing_router)
    app.include_router(observations_router)
    app.include_router(entities_router)
    app.include_router(events_router)
    app.include_router(analysis_router)
    app.include_router(findings_router)
    app.include_router(reviews_router)
    app.include_router(overrides_router)
    app.include_router(triage_router)
    app.include_router(questions_router)
    app.include_router(transcripts_router)
    return app


async def get_database(request: Request) -> SQLiteDatabase:
    """Dependency for future routes; each caller owns its connection context."""
    return request.app.state.database
