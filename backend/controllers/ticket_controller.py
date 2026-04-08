from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from domain.schemas import (
    CreateTicketRequest,
    TicketResponse,
    TicketListResponse,
    TicketAnalyticsResponse,
    SendMessageRequest,
    CloseTicketRequest,
)
from services.ticket_service import TicketService
from controllers.auth_controller import _get_current_user

router = APIRouter(prefix="/tickets", tags=["tickets"])

# Cached instance (overridden by main.py dependency_overrides)
_ticket_svc: Optional[TicketService] = None


def _get_ticket_service() -> TicketService:
    """Factory per DI — iniettata in main.py."""
    if _ticket_svc:
        return _ticket_svc
    raise NotImplementedError("TicketService not wired in main.py")


def _require_operator(user: dict) -> None:
    """Solleva 403 se l'utente non è un operatore."""
    if user.get("role") not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Accesso riservato agli operatori")


def _require_customer(user: dict) -> None:
    """Solleva 403 se l'utente non è un cliente (customer o admin)."""
    if user.get("role") not in ("customer", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Accesso non consentito")


@router.get("", response_model=TicketListResponse)
def list_open_tickets(
    user: dict = Depends(_get_current_user),
    ticket_svc: TicketService = Depends(_get_ticket_service),
):
    """Lista di tutti i ticket aperti o in lavorazione (operatori)."""
    _require_operator(user)
    tickets = ticket_svc.get_open_tickets()
    return {"tickets": tickets}


@router.post("", response_model=TicketResponse)
def create_ticket(
    body: CreateTicketRequest,
    user: dict = Depends(_get_current_user),
    ticket_svc: TicketService = Depends(_get_ticket_service),
):
    """Crea un ticket di assistenza per la sessione corrente (cliente)."""
    _require_customer(user)

    ticket = ticket_svc.create_ticket(body.session_id, user["cod_cli"])
    return {"ticket": ticket}


@router.get("/session/{session_id}", response_model=TicketResponse)
def get_ticket_by_session(
    session_id: int,
    user: dict = Depends(_get_current_user),
    ticket_svc: TicketService = Depends(_get_ticket_service),
):
    """Ritorna il ticket associato a una sessione (cliente proprietario)."""
    _require_customer(user)

    # Filtra per cod_cli per evitare che un cliente veda ticket di altri
    ticket = ticket_svc.get_ticket_by_session(session_id, user.get("cod_cli"))
    if not ticket:
        raise HTTPException(status_code=404, detail="Nessun ticket trovato per questa sessione")

    return {"ticket": ticket}


@router.get("/analytics/overview", response_model=TicketAnalyticsResponse)
def get_analytics_overview(
    days: int = Query(default=14, ge=7, le=90),
    user: dict = Depends(_get_current_user),
    ticket_svc: TicketService = Depends(_get_ticket_service),
):
    """Metriche aggregate in sola lettura per dashboard operatore."""
    _require_operator(user)
    overview = ticket_svc.get_platform_usage_overview(days=days)
    return {"overview": overview}


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    user: dict = Depends(_get_current_user),
    ticket_svc: TicketService = Depends(_get_ticket_service),
):
    """Dettaglio di un ticket (operatori)."""
    _require_operator(user)

    ticket = ticket_svc.get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket non trovato")

    return {"ticket": ticket}


@router.patch("/{ticket_id}/lock")
async def lock_ticket(
    ticket_id: int,
    user: dict = Depends(_get_current_user),
    ticket_svc: TicketService = Depends(_get_ticket_service),
):
    """Locka un ticket assegnandolo all'operatore corrente (operatori)."""
    _require_operator(user)

    success = await ticket_svc.lock_ticket(ticket_id, user["userId"])
    if not success:
        raise HTTPException(status_code=409, detail="Ticket gia in lavorazione o gia chiuso")

    return {"success": True}


@router.post("/{ticket_id}/message")
async def send_ticket_message(
    ticket_id: int,
    body: SendMessageRequest,
    user: dict = Depends(_get_current_user),
    ticket_svc: TicketService = Depends(_get_ticket_service),
):
    """Invia un messaggio come operatore nella chat del ticket (operatori)."""
    _require_operator(user)

    try:
        result = await ticket_svc.send_chat_message(ticket_id, body.content)
        return {"success": True, "message_id": result["id"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{ticket_id}/unlock")
async def unlock_ticket(
    ticket_id: int,
    user: dict = Depends(_get_current_user),
    ticket_svc: TicketService = Depends(_get_ticket_service),
):
    """Rilascia il lock sull'operatore (operatori)."""
    _require_operator(user)

    await ticket_svc.unlock_ticket(ticket_id)
    return {"success": True}


@router.patch("/{ticket_id}/close")
async def close_ticket(
    ticket_id: int,
    body: Optional[CloseTicketRequest] = None,
    user: dict = Depends(_get_current_user),
    ticket_svc: TicketService = Depends(_get_ticket_service),
):
    """Chiude un ticket (operatore o cliente proprietario della sessione)."""
    ticket = ticket_svc.get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket non trovato")

    # Operatore: puo chiudere qualsiasi ticket
    if user.get("role") in ("admin", "operator"):
        closed_by = body.closed_by if body else "operator"
        await ticket_svc.close_ticket(ticket_id, closed_by=closed_by)
        return {"success": True}

    # Cliente: puo chiudere solo i propri ticket
    _require_customer(user)
    if ticket.get("cod_cli") != user["cod_cli"]:
        raise HTTPException(status_code=403, detail="Accesso non consentito")

    await ticket_svc.close_ticket(ticket_id, closed_by="customer")
    return {"success": True}


@router.patch("/session/{session_id}/close")
async def close_ticket_by_session(
    session_id: int,
    body: Optional[CloseTicketRequest] = None,
    user: dict = Depends(_get_current_user),
    ticket_svc: TicketService = Depends(_get_ticket_service),
):
    """Chiude il ticket associato a una sessione (cliente proprietario)."""
    _require_customer(user)

    # Filtra per cod_cli per sicurezza
    ticket = ticket_svc.get_ticket_by_session(session_id, user.get("cod_cli"))
    if not ticket:
        raise HTTPException(status_code=404, detail="Nessun ticket trovato per questa sessione")

    closed_by = body.closed_by if body else "customer"
    await ticket_svc.close_ticket_by_session(session_id, closed_by=closed_by, cod_cli=user.get("cod_cli"))
    return {"success": True}


@router.post("/session/{session_id}/message")
async def send_customer_message(
    session_id: int,
    body: SendMessageRequest,
    user: dict = Depends(_get_current_user),
    ticket_svc: TicketService = Depends(_get_ticket_service),
):
    """Invia un messaggio del cliente nella chat del ticket (customer side)."""
    _require_customer(user)

    try:
        result = await ticket_svc.save_customer_message(session_id, body.content)
        return {"success": True, "message_id": result["id"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
