import asyncio
import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from config import get_settings
from services.auth_service import AuthService
from services.sse_broadcaster import get_broadcaster, OPERATOR_CHANNEL

router = APIRouter(tags=["sse"])
logger = logging.getLogger(__name__)

KEEPALIVE_INTERVAL = 30  # secondi

# Cached instances (wired from main.py)
_sse_auth_svc: AuthService | None = None

def _get_sse_auth_service() -> AuthService:
    """Factory per DI — iniettata da main.py."""
    if _sse_auth_svc:
        return _sse_auth_svc
    raise NotImplementedError("AuthService not wired in main.py")

def _get_current_user(request: Request) -> dict:
    """Middleware di autenticazione SSE: estrae e valida il JWT dal cookie."""
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Non autenticato")

    auth = _get_sse_auth_service()
    payload = auth.verify_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token non valido o scaduto")

    return {
        "userId": int(payload["sub"]),
        "cod_cli": payload.get("cod_cli", 0),
        "role": payload.get("role", "customer"),
    }

def _event_stream(
    request: Request,
    channel_id: int,
    user: dict,
) -> StreamingResponse:
    """Generatore che yields eventi SSE al client."""
    broadcaster = get_broadcaster()

    async def generator():
        queue = await broadcaster.subscribe(channel_id)
        try:
            # Conferma iniziale di connessione
            yield broadcaster._format_event("connected", {"channel_id": channel_id})

            while True:
                try:
                    # Timeout per permettere a uvicorn di gestire altre richieste
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                    yield event
                except asyncio.TimeoutError:
                    # Keepalive per evitare timeout del proxy/browser
                    yield f": keepalive\n\n"

        except asyncio.CancelledError:
            pass  # Client disconnesso
        finally:
            await broadcaster.unsubscribe(channel_id, queue)
            logger.info(f"SSE stream closed for channel_id={channel_id}")

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/sse/tickets")
async def sse_tickets(
    request: Request,
    user: dict = Depends(_get_current_user),
):
    """
    Stream SSE per aggiornamenti lista ticket (solo operatori).
    Canale speciale = OPERATOR_CHANNEL (0).
    """
    if user.get("role") not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Accesso riservato agli operatori")
    return _event_stream(request, OPERATOR_CHANNEL, user)

@router.get("/sse/{session_id}")
async def sse_session(
    session_id: int,
    request: Request,
    user: dict = Depends(_get_current_user),
):
    """
    Stream SSE per aggiornamenti real-time su una sessione.
    - Riceve messaggi chat (user, ai, operator, system)
    - Riceve aggiornamenti stato ticket
    - Auth via JWT cookie.
    """
    if session_id <= 0:
        raise HTTPException(status_code=400, detail="session_id must be positive")
    return _event_stream(request, session_id, user)
