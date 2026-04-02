# ===========================================================================
# ports/i_order_repository.py — Outbound Port per ordini
#
# Astrae la persistenza e il recupero degli ordini.
# ===========================================================================

from abc import ABC, abstractmethod
from typing import Optional


class IOrderRepository(ABC):
    """Contratto di accesso ai dati ordini."""

    @abstractmethod
    def create_order(self, cod_cli: int, user_id: int,
                     session_id: Optional[int],
                     items: list[dict]) -> int:
        """Crea un ordine con le sue righe. Ritorna l'ID ordine."""
        ...

    @abstractmethod
    def get_orders_by_client(self, cod_cli: int, page: int = 0,
                             limit: int = 15) -> list[dict]:
        """Recupera ordini del cliente con paginazione."""
        ...

    @abstractmethod
    def get_order_detail(self, order_id: int, cod_cli: int) -> Optional[dict]:
        """Recupera il dettaglio completo di un ordine (header + items + messages)."""
        ...
