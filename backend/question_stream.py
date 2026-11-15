"""Bounded live answer transport; drafts are replaced by the checked final answer."""
import asyncio
import json
import queue
import threading
from starlette.responses import StreamingResponse
from backend.errors import AccessError

_slots = threading.BoundedSemaphore(4)

class StreamCancelled(BaseException):
    pass


def stream_answer(request, grant, run):
    if not _slots.acquire(blocking=False):
        raise AccessError(429, 'BUSY', 'All answer slots are busy. Retry shortly.')
    messages = queue.Queue(maxsize=32)
    stopped = threading.Event()

    def emit(kind, value):
        if stopped.is_set():
            raise StreamCancelled()
        if not request.app.state.case_access.allows(grant.actor.id, grant.case_id):
            raise StreamCancelled()
        while not stopped.is_set():
            try:
                messages.put(dict(type=kind, **value), timeout=.1)
                return
            except queue.Full:
                pass
        raise StreamCancelled()

    def worker():
        try:
            emit('status', dict(stage='searching'))
            answer = run(emit)
            emit('done', dict(answer=answer))
        except StreamCancelled:
            pass
        except Exception:
            try:
                emit('error', dict(message='Could not complete the response. Retry.'))
            except StreamCancelled:
                pass
        finally:
            _slots.release()

    async def events():
        threading.Thread(target=worker, daemon=True).start()
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    message = messages.get_nowait()
                except queue.Empty:
                    if not request.app.state.case_access.allows(grant.actor.id, grant.case_id):
                        return
                    await asyncio.sleep(.05)
                    continue
                if not request.app.state.case_access.allows(grant.actor.id, grant.case_id):
                    return
                yield json.dumps(message, ensure_ascii=False) + '\n'
                if message['type'] in ('done', 'error'):
                    return
        finally:
            stopped.set()

    return StreamingResponse(events(), media_type='application/x-ndjson',
                             headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
