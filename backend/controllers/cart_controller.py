from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from adapters.postgres_adapter import PostgresAdapter
from domain.schemas import CartActionRequest, AddByNameRequest
from controllers.auth_controller import _get_current_user
from services.cart_service import CartService

router = APIRouter(tags=["cart"])


def _get_cart_service() -> CartService:
    """Factory per DI — iniettata in main.py."""
    raise NotImplementedError("Override in main.py")


def _get_db_adapter() -> PostgresAdapter:
    """Factory per DI — iniettata in main.py."""
    raise NotImplementedError("Override in main.py")


def _assert_session_access(session_id: int, user: dict, db: PostgresAdapter) -> None:
    role = str(user.get("role") or "customer")

    if role in ("admin", "operator"):
        ticket = db.get_ticket_by_session(session_id)
        if not ticket:
            raise HTTPException(status_code=403, detail="Sessione non associata a ticket")
        if ticket.get("status") != "in_lavorazione":
            raise HTTPException(status_code=403, detail="Ticket non in lavorazione")
        if int(ticket.get("locked_by") or 0) != int(user["userId"]):
            raise HTTPException(status_code=403, detail="Ticket non in carico all'operatore corrente")
        return

    session = db.get_active_session(int(user["userId"]))
    if not session or int(session["id"]) != int(session_id):
        raise HTTPException(status_code=403, detail="Sessione non autorizzata")


@router.get("/cart")
def get_cart(session_id: Optional[int] = None,
             user: dict = Depends(_get_current_user),
             cart_service: CartService = Depends(_get_cart_service),
             db: PostgresAdapter = Depends(_get_db_adapter)):
    if session_id:
        _assert_session_access(session_id, user, db)
        return cart_service.get_cart_by_session(session_id)
    items = cart_service.get_cart(user["userId"])
    return items


@router.post("/cart")
def cart_action(body: CartActionRequest,
                user: dict = Depends(_get_current_user),
                cart_service: CartService = Depends(_get_cart_service),
                db: PostgresAdapter = Depends(_get_db_adapter)):
    if body.session_id:
        _assert_session_access(body.session_id, user, db)

    if body.action == "add":
        if not body.cod_art or not body.qta:
            raise HTTPException(status_code=400, detail="cod_art e qta obbligatori")
        try:
            result = cart_service.add_to_cart(
                user_id=user["userId"],
                cod_art=body.cod_art,
                qta=body.qta,
                source=body.source or "customer",
                ai_confidence=body.ai_confidence,
                related_message_id=body.related_message_id,
                session_id=body.session_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"success": True, **result}

    elif body.action == "remove":
        if not body.id:
            raise HTTPException(status_code=400, detail="id obbligatorio per remove")
        removed = cart_service.remove_from_cart(body.id, user["userId"], session_id=body.session_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Articolo non trovato nel carrello")
        return {"success": True}

    elif body.action == "update_quantity":
        if not body.id or body.qta is None:
            raise HTTPException(status_code=400, detail="id e qta obbligatori")
        updated = cart_service.update_cart_quantity(
            body.id, user["userId"], body.qta, body.source or "customer",
            session_id=body.session_id,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Articolo non trovato nel carrello")
        return {"success": True}

    else:
        raise HTTPException(status_code=400, detail=f"Azione non valida: {body.action}")


@router.post("/cart/add-by-name")
def add_by_name(body: AddByNameRequest,
                user: dict = Depends(_get_current_user),
                cart_service: CartService = Depends(_get_cart_service),
                db: PostgresAdapter = Depends(_get_db_adapter)):
    if body.session_id:
        _assert_session_access(body.session_id, user, db)

    client_id = int(user["userId"])

    product = db.find_product_by_name(body.product_name, client_id)
    if not product:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")

    cod_art = product["cod_art"]

    try:
        result = cart_service.add_to_cart(
            user_id=client_id,
            cod_art=cod_art,
            qta=body.qta,
            source="customer",
            session_id=body.session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"success": True, **result}
