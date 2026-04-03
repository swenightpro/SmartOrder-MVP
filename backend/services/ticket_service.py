from typing import Optional

from ports.i_ticket_repository import ITicketRepository
from services.sse_broadcaster import OPERATOR_CHANNEL

class TicketService:
    """Servizio applicativo per la gestione dei ticket di assistenza."""

    def __init__(self, ticket_repo: ITicketRepository, db_adapter=None, broadcaster=None):
        self._ticket_repo = ticket_repo
        self._db = db_adapter  # PostgresAdapter per messaggi e sessioni
        self._broadcaster = broadcaster

    # =======================================================================
    # Use cases
    # =======================================================================

    def create_ticket(self, session_id: int, cod_cli: int) -> dict:
        """Crea un ticket, aggiunge un messaggio di sistema nella chat, ritorna il ticket."""
        ticket = self._ticket_repo.create_ticket(session_id, cod_cli)

        # Aggiunge un messaggio di sistema nella chat per segnalare l'apertura del ticket
        if self._db is not None:
            self._db.save_message(
                session_id=session_id,
                sender="system",
                content="Un operatore è stato allertato e risponderà a breve. "
                        "Il ticket di assistenza è stato aperto.",
            )

        return ticket

    def get_open_tickets(self) -> list[dict]:
        """Ritorna i ticket aperti/in lavorazione arricchiti con rag_soc e tempo di attesa."""
        tickets = self._ticket_repo.get_open_tickets()

        for ticket in tickets:
            # Calcola tempo di attesa in minuti
            if ticket.get("created_at"):
                ticket["waiting_minutes"] = self._calc_waiting_time(ticket["created_at"]) / 60

            # Recupera ragione sociale del cliente
            if self._db is not None and ticket.get("cod_cli"):
                client = self._db.get_client_info(ticket["cod_cli"])
                ticket["rag_soc"] = client["rag_soc"] if client else ""

        return tickets

    def get_ticket_by_id(self, ticket_id: int) -> Optional[dict]:
        """Ritorna il ticket con dati arricchiti (rag_soc, messaggi)."""
        ticket = self._ticket_repo.get_ticket_by_id(ticket_id)
        if not ticket:
            return None

        if self._db is not None:
            # Arricchisci con rag_soc
            if ticket.get("cod_cli"):
                client = self._db.get_client_info(ticket["cod_cli"])
                ticket["rag_soc"] = client["rag_soc"] if client else ""

            # Recupera messaggi e carrello della sessione
            if ticket.get("session_id"):
                messages = self._db.get_messages(ticket["session_id"])
                ticket["messages"] = messages
                cart_items = self._db.get_cart_by_session(ticket["session_id"])
                ticket["cart_items"] = cart_items

        return ticket

    async def lock_ticket(self, ticket_id: int, operator_id: int) -> bool:
        """Locka il ticket per un operatore. Ritorna True se riuscito."""
        result = self._ticket_repo.lock_ticket(ticket_id, operator_id)
        if result and self._broadcaster:
            ticket = self._ticket_repo.get_ticket_by_id(ticket_id)
            if ticket and ticket.get("session_id"):
                await self._broadcaster.emit(ticket["session_id"], "ticket_update", {
                    "ticket_id": ticket_id,
                    "status": "in_lavorazione",
                    "session_id": ticket["session_id"],
                    "locked_by": operator_id,
                })
                await self._broadcaster.emit(OPERATOR_CHANNEL, "ticket_update", {
                    "ticket_id": ticket_id,
                    "status": "in_lavorazione",
                    "session_id": ticket["session_id"],
                    "locked_by": operator_id,
                })
        return result

    async def unlock_ticket(self, ticket_id: int) -> None:
        """Rilascia il lock dell'operatore sul ticket."""
        ticket = self._ticket_repo.get_ticket_by_id(ticket_id)
        self._ticket_repo.unlock_ticket(ticket_id)
        if self._broadcaster and ticket and ticket.get("session_id"):
            session_id = ticket["session_id"]
            await self._broadcaster.emit(session_id, "ticket_update", {
                "ticket_id": ticket_id,
                "status": "aperto",
                "session_id": session_id,
                "locked_by": None,
            })
            await self._broadcaster.emit(OPERATOR_CHANNEL, "ticket_update", {
                "ticket_id": ticket_id,
                "status": "aperto",
                "session_id": session_id,
                "locked_by": None,
            })

    async def close_ticket(self, ticket_id: int, closed_by: str = "operator") -> None:
        """Chiude il ticket, riabilita l'AI e aggiunge messaggio di sistema."""
        ticket = self._ticket_repo.get_ticket_by_id(ticket_id)
        self._ticket_repo.close_ticket(ticket_id)

        if self._db is not None and ticket:
            session_id = ticket.get("session_id")
            if session_id:
                if closed_by == "operator":
                    content = "Il ticket è stato chiuso dall'operatore. L'assistente AI è di nuovo disponibile per questa sessione."
                else:
                    content = "Il ticket è stato chiuso dal cliente. L'assistente AI è di nuovo disponibile per questa sessione."
                self._db.save_message(
                    session_id=session_id,
                    sender="system",
                    content=content,
                )
                if self._broadcaster:
                    await self._broadcaster.emit(session_id, "ticket_update", {
                        "ticket_id": ticket_id,
                        "status": "chiuso",
                        "session_id": session_id,
                    })
                    await self._broadcaster.emit(OPERATOR_CHANNEL, "ticket_update", {
                        "ticket_id": ticket_id,
                        "status": "chiuso",
                        "session_id": session_id,
                    })

    async def send_chat_message(self, ticket_id: int, content: str) -> dict:
        """Invia un messaggio come operatore nella chat della sessione."""
        ticket = self._ticket_repo.get_ticket_by_id(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} non trovato")
        if ticket.get("status") == "chiuso":
            raise ValueError("Impossibile inviare messaggi: ticket chiuso")
        session_id = ticket.get("session_id")
        if not session_id:
            raise ValueError("Ticket senza sessione associata")
        msg_id = self._db.send_message(session_id, "operator", content)
        msg_data = {
            "id": msg_id,
            "sender": "operator",
            "content": content,
        }
        if self._broadcaster:
            await self._broadcaster.emit(session_id, "message", msg_data)
        return msg_data

    def get_ticket_by_session(self, session_id: int, cod_cli: Optional[int] = None) -> Optional[dict]:
        """Ritorna il ticket associato a una sessione, con arricchimento dati."""
        ticket = self._ticket_repo.get_ticket_by_session(session_id, cod_cli)
        if not ticket:
            return None

        if self._db is not None:
            if ticket.get("cod_cli"):
                client = self._db.get_client_info(ticket["cod_cli"])
                ticket["rag_soc"] = client["rag_soc"] if client else ""

        return ticket

    async def close_ticket_by_session(self, session_id: int, closed_by: str = "customer", cod_cli: Optional[int] = None) -> None:
        """Chiude il ticket associato a una sessione."""
        ticket = self._ticket_repo.get_ticket_by_session(session_id, cod_cli)
        if not ticket:
            return
        await self.close_ticket(ticket["id"], closed_by=closed_by)

    async def save_customer_message(self, session_id: int, content: str) -> dict:
        """Salva un messaggio del cliente e lo notifica via SSE all'operatore."""
        msg_id = self._db.send_message(session_id, "user", content)
        msg_data = {
            "id": msg_id,
            "sender": "user",
            "content": content,
        }
        # Notifica l'operatore in tempo reale su entrambi i canali:
        # - OPERATOR_CHANNEL: per la lista ticket (aggiorna count, ecc.)
        # - session_id: per TicketSubentroModal che sottoscrive /sse/{session_id}
        if self._broadcaster:
            await self._broadcaster.emit(OPERATOR_CHANNEL, "message", {
                **msg_data,
                "session_id": session_id,
            })
            await self._broadcaster.emit(session_id, "message", msg_data)
        return msg_data

    # =======================================================================
    # Helpers
    # =======================================================================

    def _calc_waiting_time(self, created_at: str) -> float:
        """Calcola i secondi trascorsi dalla creazione del ticket."""
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo

            created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            now = datetime.now(ZoneInfo("Europe/Rome"))
            return max(0.0, (now - created).total_seconds())
        except Exception:
            return 0.0
