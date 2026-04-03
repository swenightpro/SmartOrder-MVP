import asyncio
from typing import Optional
from ports.i_order_repository import IOrderRepository
from ports.i_session_manager import ISessionManager

class OrderService:
    def __init__(self, order_repo: IOrderRepository, session_manager: ISessionManager,
                 broadcaster=None):
        self._repo = order_repo
        self._session_manager = session_manager
        self._broadcaster = broadcaster

    def _schedule_emit(self, coro) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
            return
        loop.create_task(coro)

    def create_order(self, cod_cli: int, user_id: int,
                     session_id: Optional[int], items: list[dict]) -> int:
        order_id = self._repo.create_order(cod_cli, user_id, session_id, items)
        # Svuota il carrello dopo la creazione dell'ordine
        if session_id:
            self._session_manager.clear_cart_by_session(session_id)
        else:
            self._session_manager.clear_cart(user_id)
        # Notifica SSE per aggiornare il carrello in tempo reale
        if self._broadcaster and session_id:
            self._schedule_emit(
                self._broadcaster.emit(session_id, "cart_update", {"action": "cleared"})
            )
        return order_id

    def get_orders_by_client(self, cod_cli: int, page: int = 0, limit: int = 15,
                             search: str = "", sort_by: str = "data_ord",
                             sort_dir: str = "desc",
                             date_from: Optional[str] = None,
                             date_to: Optional[str] = None) -> list[dict]:
        return self._repo.get_orders_by_client(
            cod_cli, page, limit, search, sort_by, sort_dir, date_from, date_to)

    def get_all_orders(self, page: int = 0, limit: int = 15,
                      search: str = "", sort_by: str = "data_ord",
                      sort_dir: str = "desc",
                      date_from: Optional[str] = None,
                      date_to: Optional[str] = None,
                      search_cod_cli: str = "",
                      search_rag_soc: str = "") -> list[dict]:
        return self._repo.get_all_orders(
            page, limit, search, sort_by, sort_dir, date_from, date_to,
            search_cod_cli, search_rag_soc)

    def get_order_detail(self, order_id: int, cod_cli: int) -> Optional[dict]:
        return self._repo.get_order_detail(order_id, cod_cli)
