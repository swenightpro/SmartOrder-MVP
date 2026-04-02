# ===========================================================================
# controllers/order_controller.py — Controller ordini (Layer 1)
#
# Endpoint: POST /orders/create, GET /orders/list, GET /orders/detail
# ===========================================================================

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from domain.schemas import CreateOrderRequest
from controllers.auth_controller import _get_current_user
from services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


def _get_order_service() -> OrderService:
    """Factory per DI — iniettata in main.py."""
    raise NotImplementedError("Override in main.py")


def _resolve_target_cod_cli(user: dict, requested_cod_cli: Optional[int]) -> int:
    role = str(user.get("role") or "customer")
    user_cod_cli = int(user.get("cod_cli") or 0)

    if role == "admin":
        if requested_cod_cli is None:
            raise HTTPException(status_code=400, detail="cod_cli obbligatorio per utente admin")
        return int(requested_cod_cli)

    if user_cod_cli <= 0:
        raise HTTPException(status_code=400, detail="Utente senza cod_cli valido")

    if requested_cod_cli is not None and int(requested_cod_cli) != user_cod_cli:
        raise HTTPException(status_code=403, detail="cod_cli non autorizzato")

    return user_cod_cli


@router.post("/create")
def create_order(body: CreateOrderRequest,
                 user: dict = Depends(_get_current_user),
                 order_service: OrderService = Depends(_get_order_service)):
    if not body.items:
        raise HTTPException(status_code=400, detail="Nessun articolo nell'ordine")

    target_cod_cli = _resolve_target_cod_cli(user, body.cod_cli)
    items_dicts = [item.model_dump() for item in body.items]
    try:
        order_id = order_service.create_order(
            cod_cli=target_cod_cli,
            user_id=user["userId"],
            session_id=body.session_id,
            items=items_dicts,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"order_id": order_id}


@router.get("/list")
def list_orders(page: int = 0,
                cod_cli: Optional[int] = None,
                user: dict = Depends(_get_current_user),
                order_service: OrderService = Depends(_get_order_service)):
    target_cod_cli = _resolve_target_cod_cli(user, cod_cli)
    orders = order_service.get_orders_by_client(target_cod_cli, page)
    return orders


@router.get("/detail")
def order_detail(id: int,
                 cod_cli: Optional[int] = None,
                 user: dict = Depends(_get_current_user),
                 order_service: OrderService = Depends(_get_order_service)):
    target_cod_cli = _resolve_target_cod_cli(user, cod_cli)
    detail = order_service.get_order_detail(id, target_cod_cli)
    if not detail:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    return detail
