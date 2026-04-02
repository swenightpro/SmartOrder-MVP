# ===========================================================================
# controllers/cart_controller.py — Controller carrello (Layer 1)
#
# Endpoint: GET /cart, POST /cart
# ===========================================================================

from fastapi import APIRouter, Depends, HTTPException
from domain.schemas import CartActionRequest
from controllers.auth_controller import _get_current_user
from services.cart_service import CartService

router = APIRouter(tags=["cart"])


def _get_cart_service() -> CartService:
    """Factory per DI — iniettata in main.py."""
    raise NotImplementedError("Override in main.py")


@router.get("/cart")
def get_cart(user: dict = Depends(_get_current_user),
             cart_service: CartService = Depends(_get_cart_service)):
    items = cart_service.get_cart(user["userId"])
    return items


@router.post("/cart")
def cart_action(body: CartActionRequest,
                user: dict = Depends(_get_current_user),
                cart_service: CartService = Depends(_get_cart_service)):
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
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"success": True, **result}

    elif body.action == "remove":
        if not body.id:
            raise HTTPException(status_code=400, detail="id obbligatorio per remove")
        removed = cart_service.remove_from_cart(body.id, user["userId"])
        if not removed:
            raise HTTPException(status_code=404, detail="Articolo non trovato nel carrello")
        return {"success": True}

    elif body.action == "update_quantity":
        if not body.id or body.qta is None:
            raise HTTPException(status_code=400, detail="id e qta obbligatori")
        updated = cart_service.update_cart_quantity(
            body.id, user["userId"], body.qta, body.source or "customer"
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Articolo non trovato nel carrello")
        return {"success": True}

    else:
        raise HTTPException(status_code=400, detail=f"Azione non valida: {body.action}")
