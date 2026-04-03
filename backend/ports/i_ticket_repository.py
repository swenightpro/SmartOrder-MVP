from abc import ABC, abstractmethod
from typing import Optional

class ITicketRepository(ABC):
    """Contratto di accesso ai dati ticket di assistenza."""

    @abstractmethod
    def create_ticket(self, session_id: int, cod_cli: int) -> dict:
        """Crea un nuovo ticket e lo ritorna (include id)."""
        ...

    @abstractmethod
    def get_ticket_by_session(self, session_id: int, cod_cli: Optional[int] = None) -> Optional[dict]:
        """Recupera il ticket attivo per una sessione, opzionalmente filtrato per cod_cli. Ritorna None se non trovato."""
        ...

    @abstractmethod
    def get_open_tickets(self) -> list[dict]:
        """Ritorna tutti i ticket aperti o in lavorazione, ordinati per attesa decrescente."""
        ...

    @abstractmethod
    def get_ticket_by_id(self, ticket_id: int) -> Optional[dict]:
        """Recupera un ticket per ID. Ritorna None se non trovato."""
        ...

    @abstractmethod
    def lock_ticket(self, ticket_id: int, operator_id: int) -> bool:
        """Imposta lo stato 'in_lavorazione' e locked_by. Ritorna True se riuscito."""
        ...

    @abstractmethod
    def unlock_ticket(self, ticket_id: int) -> None:
        """Rilascia il lock sull'operatore, mantiene lo stato corrente."""
        ...

    @abstractmethod
    def close_ticket(self, ticket_id: int) -> None:
        """Imposta lo stato 'chiuso' e rilascia il lock."""
        ...

    @abstractmethod
    def get_last_message_time(self, session_id: int) -> Optional[str]:
        """Ritorna il timestamp dell'ultimo messaggio nella sessione, o None."""
        ...

    @abstractmethod
    def send_message(self, session_id: int, sender: str, content: str) -> int:
        """Salva un messaggio nella chat. Ritorna l'ID del messaggio."""
        ...
