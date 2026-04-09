import asyncio
import dataclasses
from typing import Optional
from ports.i_session_manager import ISessionManager

class CartService:
    def __init__(self, session_manager: ISessionManager, broadcaster=None):
        self._repo = session_manager
        self._broadcaster = broadcaster

    def _schedule_emit(self, coro) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
            return
        loop.create_task(coro)

    def _emit_cart_update(self, session_id: Optional[int]) -> None:
        if self._broadcaster and session_id:
            self._schedule_emit(self._broadcaster.emit(session_id, "cart_update", {}))

    def get_cart(self, user_id: int) -> list[dict]:
        items = self._repo.get_cart(user_id)
        return [dataclasses.asdict(item) for item in items]

    def get_cart_by_session(self, session_id: int) -> list[dict]:
        items = self._repo.get_cart_by_session(session_id)
        return [dataclasses.asdict(item) for item in items]

    def add_to_cart(self, user_id: int, cod_art: str, qta: int,
                    source: str = "customer",
                    ai_confidence: Optional[float] = None,
                    related_message_id: Optional[int] = None,
                    session_id: Optional[int] = None) -> dict:
        if session_id:
            result = self._repo.add_to_cart_by_session(
                session_id, cod_art, qta, source,
                ai_confidence, related_message_id
            )
        else:
            result = self._repo.add_to_cart(
                user_id, cod_art, qta, source,
                ai_confidence, related_message_id
            )
        self._emit_cart_update(session_id)
        return dataclasses.asdict(result)

    def remove_from_cart(self, cart_item_id: int, user_id: int,
                        session_id: Optional[int] = None) -> bool:
        if session_id:
            result = self._repo.remove_from_cart_by_session(cart_item_id, session_id)
        else:
            result = self._repo.remove_from_cart(cart_item_id, user_id)
        self._emit_cart_update(session_id)
        return result

    def update_cart_quantity(self, cart_item_id: int, user_id: int,
                             qta: int, source: str = "customer",
                             session_id: Optional[int] = None) -> bool:
        if session_id:
            result = self._repo.update_cart_quantity_by_session(cart_item_id, session_id, qta, source)
        else:
            result = self._repo.update_cart_quantity(cart_item_id, user_id, qta, source)
        self._emit_cart_update(session_id)
        return result

    def clear_cart(self, user_id: int, session_id: Optional[int] = None) -> None:
        self._repo.clear_cart(user_id)
        self._emit_cart_update(session_id)
