from abc import ABC, abstractmethod
from typing import Optional

from domain.models import Ticket


class ITicketRepository(ABC):
    """Contratto di accesso ai dati ticket di assistenza."""

    @abstractmethod
    def create_ticket(self, session_id: int, cod_cli: int) -> Ticket:
        """Crea un nuovo ticket e lo ritorna."""
        ...

    @abstractmethod
    def get_ticket_by_session(self, session_id: int, cod_cli: Optional[int] = None) -> Optional[Ticket]:
        """Recupera il ticket attivo per una sessione. Ritorna None se non trovato."""
        ...

    @abstractmethod
    def get_open_tickets(self) -> list[Ticket]:
        """Ritorna tutti i ticket aperti o in lavorazione."""
        ...

    @abstractmethod
    def get_ticket_by_id(self, ticket_id: int) -> Optional[Ticket]:
        """Recupera un ticket per ID. Ritorna None se non trovato."""
        ...

    @abstractmethod
    def lock_ticket(self, ticket_id: int, operator_id: int) -> bool:
        """Imposta lo stato 'in_lavorazione' e locked_by. Ritorna True se riuscito."""
        ...

    @abstractmethod
    def unlock_ticket(self, ticket_id: int) -> None:
        """Rilascia il lock sull'operatore."""
        ...

    @abstractmethod
    def close_ticket(self, ticket_id: int) -> None:
        """Imposta lo stato 'chiuso'."""
        ...

    @abstractmethod
    def get_platform_usage_overview(self, days: int = 14) -> dict:
        """Ritorna metriche aggregate in sola lettura per dashboard operatore."""
        ...

    @abstractmethod
    def get_last_message_time(self, session_id: int) -> Optional[str]:
        """Ritorna il timestamp dell'ultimo messaggio nella sessione, o None."""
        ...

    @abstractmethod
    def send_message(self, session_id: int, sender: str, content: str) -> int:
        """Salva un messaggio nella chat. Ritorna l'ID del messaggio."""
        ...
