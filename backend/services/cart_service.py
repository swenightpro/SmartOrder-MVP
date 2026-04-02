# ===========================================================================
# services/cart_service.py — Application Service per carrello
#
# Gestisce la logica di business relativa al carrello.
# ===========================================================================

from typing import Optional
from ports.i_session_manager import ISessionManager

class CartService:
    def __init__(self, session_manager: ISessionManager):
        self._repo = session_manager

    def get_cart(self, user_id: int) -> list[dict]:
        return self._repo.get_cart(user_id)

    def add_to_cart(self, user_id: int, cod_art: str, qta: int,
                    source: str = "customer",
                    ai_confidence: Optional[float] = None,
                    related_message_id: Optional[int] = None) -> dict:
        return self._repo.add_to_cart(
            user_id, cod_art, qta, source,
            ai_confidence, related_message_id
        )

    def remove_from_cart(self, cart_item_id: int, user_id: int) -> bool:
        return self._repo.remove_from_cart(cart_item_id, user_id)

    def update_cart_quantity(self, cart_item_id: int, user_id: int,
                             qta: int, source: str = "customer") -> bool:
        return self._repo.update_cart_quantity(cart_item_id, user_id, qta, source)

    def clear_cart(self, user_id: int) -> None:
        self._repo.clear_cart(user_id)
