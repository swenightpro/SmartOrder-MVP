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
                             limit: int = 15,
                             search: str = "",
                             sort_by: str = "data_ord",
                             sort_dir: str = "desc",
                             date_from: Optional[str] = None,
                             date_to: Optional[str] = None) -> list[dict]:
        """Recupera ordini del cliente con paginazione e filtri."""
        ...

    @abstractmethod
    def get_all_orders(self, page: int = 0, limit: int = 15,
                       search: str = "",
                       sort_by: str = "data_ord",
                       sort_dir: str = "desc",
                       date_from: Optional[str] = None,
                       date_to: Optional[str] = None,
                       search_cod_cli: str = "",
                       search_rag_soc: str = "") -> list[dict]:
        """Recupera TUTTI gli ordini (admin) con filtri e ordinamento."""
        ...

    @abstractmethod
    def get_order_detail(self, order_id: int, cod_cli: int) -> Optional[dict]:
        """Recupera il dettaglio completo di un ordine (header + items + messages)."""
        ...

    @abstractmethod
    def get_order_detail_any(self, order_id: int) -> Optional[dict]:
        """Recupera il dettaglio completo di un ordine senza filtro cod_cli (per admin)."""
        ...
