# ===========================================================================
# ports/i_user_repository.py — Outbound Port per accesso dati utente
#
# Definisce il contratto che il layer applicativo usa per interagire con
# i dati utente e gli assortimenti, senza conoscere il database sottostante.
# ===========================================================================

from abc import ABC, abstractmethod
from typing import Optional


class IUserRepository(ABC):
    """Contratto di accesso ai dati utente e assortimento."""

    @abstractmethod
    def find_by_email(self, email: str) -> Optional[dict]:
        """Recupera l'utente associato all'email. Ritorna None se non trovato."""
        ...

    @abstractmethod
    def find_by_id(self, user_id: int) -> Optional[dict]:
        """Recupera l'utente per ID. Ritorna None se non trovato."""
        ...

    @abstractmethod
    def create_user(self, email: str, password_hash: str, password_salt: str,
                    role: str, cod_cli: Optional[int]) -> dict:
        """Crea un nuovo utente e ritorna i suoi dati."""
        ...

    @abstractmethod
    def update_password(self, user_id: int, password_hash: str, password_salt: str) -> None:
        """Aggiorna hash e salt della password di un utente."""
        ...

    @abstractmethod
    def get_client_info(self, cod_cli: int) -> Optional[dict]:
        """Recupera ragione sociale e dati del cliente dalla tabella anacli."""
        ...

    @abstractmethod
    def search_clients(self, query: str, limit: int = 10) -> list[dict]:
        """Cerca clienti per ragione sociale o codice cliente."""
        ...
