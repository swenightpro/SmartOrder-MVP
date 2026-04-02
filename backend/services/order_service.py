# ===========================================================================
# services/order_service.py — Application Service per ordini
#
# Gestisce la logica di business relativa agli ordini.
# ===========================================================================

from typing import Optional
from ports.i_order_repository import IOrderRepository
from ports.i_session_manager import ISessionManager

class OrderService:
    def __init__(self, order_repo: IOrderRepository, session_manager: ISessionManager):
        self._repo = order_repo
        self._session_manager = session_manager

    def create_order(self, cod_cli: int, user_id: int,
                     session_id: Optional[int], items: list[dict]) -> int:
        order_id = self._repo.create_order(cod_cli, user_id, session_id, items)
        # Svuota il carrello dopo la creazione dell'ordine
        self._session_manager.clear_cart(user_id)
        return order_id

    def get_orders_by_client(self, cod_cli: int, page: int = 0, limit: int = 15) -> list[dict]:
        return self._repo.get_orders_by_client(cod_cli, page, limit)

    def get_order_detail(self, order_id: int, cod_cli: int) -> Optional[dict]:
        return self._repo.get_order_detail(order_id, cod_cli)
