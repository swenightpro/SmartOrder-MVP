from abc import ABC, abstractmethod
from typing import Optional

from domain.models import CartItem, Session


class ISessionManager(ABC):
    """Contratto di accesso a sessioni, messaggi e carrelli."""

    # --- Sessioni ---
    @abstractmethod
    def get_active_session(self, user_id: int) -> Optional[Session]:
        """Recupera la sessione attiva per l'utente. None se non esiste."""
        ...

    @abstractmethod
    def create_session(self, user_id: int) -> Session:
        """Crea una nuova sessione e ritorna i dati."""
        ...

    # --- Messaggi ---
    @abstractmethod
    def get_messages(self, session_id: int) -> list[dict]:
        """Recupera tutti i messaggi di una sessione, ordinati cronologicamente."""
        ...

    @abstractmethod
    def save_message(self, session_id: int, sender: str, content: str,
                     metadata: Optional[str] = None) -> int:
        """Salva un messaggio e ritorna il suo ID."""
        ...

    # --- Carrello ---
    @abstractmethod
    def get_cart_by_session(self, session_id: int) -> list[CartItem]:
        """Recupera gli articoli nel carrello di una sessione specifica."""
        ...

    @abstractmethod
    def get_cart(self, user_id: int) -> list[CartItem]:
        """Recupera gli articoli nel carrello dell'utente."""
        ...

    @abstractmethod
    def add_to_cart(self, user_id: int, cod_art: str, qta: int,
                    source: str = "customer",
                    ai_confidence: Optional[float] = None,
                    related_message_id: Optional[int] = None) -> CartItem:
        """Aggiunge un articolo al carrello (o aggiorna se esiste). Ritorna la riga."""
        ...

    @abstractmethod
    def add_to_cart_by_session(self, session_id: int, cod_art: str, qta: int,
                               source: str = "customer",
                               ai_confidence: Optional[float] = None,
                               related_message_id: Optional[int] = None) -> CartItem:
        """Aggiunge un articolo al carrello della sessione specificata."""
        ...

    @abstractmethod
    def remove_from_cart(self, cart_item_id: int, user_id: int) -> bool:
        """Rimuove un articolo dal carrello. Ritorna True se rimosso."""
        ...

    @abstractmethod
    def remove_from_cart_by_session(self, cart_item_id: int, session_id: int) -> bool:
        """Rimuove un articolo dal carrello della sessione specificata."""
        ...

    @abstractmethod
    def update_cart_quantity(self, cart_item_id: int, user_id: int,
                            qta: int, source: str = "customer") -> bool:
        """Aggiorna la quantità di un articolo nel carrello."""
        ...

    @abstractmethod
    def update_cart_quantity_by_session(self, cart_item_id: int, session_id: int,
                                        qta: int, source: str = "customer") -> bool:
        """Aggiorna la quantità di un articolo nel carrello della sessione specificata."""
        ...

    @abstractmethod
    def clear_cart(self, user_id: int) -> None:
        """Svuota il carrello dell'utente."""
        ...

    @abstractmethod
    def clear_cart_by_session(self, session_id: int) -> None:
        """Svuota il carrello della sessione specificata."""
        ...
