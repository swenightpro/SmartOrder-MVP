"""
Test di sistema: flusso completo di gestione ticket.
Verifica il percorso: cliente apre ticket → operatore lo prende in carico →
scambio messaggi → chiusura.

NOTA: Marcati con @pytest.mark.system.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from controllers import ticket_controller
from controllers.ticket_controller import _get_ticket_service
from controllers.auth_controller import _get_current_user
from services.ticket_service import TicketService


@pytest.mark.system
class TestTicketFlow:
    """ST: Flusso completo di gestione ticket assistenza"""

    @pytest.fixture
    def mock_ticket_service(self):
        svc = Mock(spec=TicketService)
        svc.lock_ticket = AsyncMock()
        svc.unlock_ticket = AsyncMock()
        svc.close_ticket = AsyncMock()
        svc.send_chat_message = AsyncMock()
        svc.close_ticket_by_session = AsyncMock()
        svc.save_customer_message = AsyncMock()
        return svc

    @pytest.fixture
    def customer_user(self):
        return {"userId": 123, "cod_cli": 456, "role": "customer"}

    @pytest.fixture
    def operator_user(self):
        return {"userId": 1, "cod_cli": 0, "role": "admin"}

    def _make_app(self, mock_svc, user):
        app = FastAPI()
        app.include_router(ticket_controller.router)
        app.dependency_overrides[_get_ticket_service] = lambda: mock_svc
        app.dependency_overrides[_get_current_user] = lambda: user
        return app

    def test_customer_opens_ticket_operator_handles_and_closes(
        self, mock_ticket_service, customer_user, operator_user
    ):
        """ST: cliente apre ticket → operatore locka → invia messaggio → chiude"""
        # Step 1: Cliente apre ticket
        customer_client = TestClient(self._make_app(mock_ticket_service, customer_user))
        mock_ticket_service.create_ticket.return_value = {
            "id": 1, "session_id": 456, "status": "aperto",
        }

        create_resp = customer_client.post("/tickets", json={"session_id": 456})
        assert create_resp.status_code == 200
        ticket_id = create_resp.json()["ticket"]["id"]

        # Step 2: Operatore vede i ticket e ne prende uno
        operator_client = TestClient(self._make_app(mock_ticket_service, operator_user))
        mock_ticket_service.get_open_tickets.return_value = [
            {"id": ticket_id, "status": "aperto"},
        ]

        list_resp = operator_client.get("/tickets")
        assert list_resp.status_code == 200
        assert len(list_resp.json()["tickets"]) == 1

        # Step 3: Operatore locka il ticket
        mock_ticket_service.lock_ticket.return_value = True

        lock_resp = operator_client.patch(f"/tickets/{ticket_id}/lock")
        assert lock_resp.status_code == 200

        # Step 4: Operatore invia messaggio
        mock_ticket_service.send_chat_message.return_value = {
            "id": 789, "sender": "operator", "content": "Come posso aiutarti?",
        }

        msg_resp = operator_client.post(f"/tickets/{ticket_id}/message", json={
            "content": "Come posso aiutarti?",
        })
        assert msg_resp.status_code == 200

        # Step 5: Operatore chiude il ticket
        mock_ticket_service.get_ticket_by_id.return_value = {
            "id": ticket_id, "session_id": 456, "cod_cli": 456,
        }

        close_resp = operator_client.patch(f"/tickets/{ticket_id}/close")
        assert close_resp.status_code == 200
        mock_ticket_service.close_ticket.assert_called_once()

    def test_customer_sends_message_and_closes_own_ticket(
        self, mock_ticket_service, customer_user
    ):
        """ST: cliente apre ticket → invia messaggio → chiude da solo"""
        client = TestClient(self._make_app(mock_ticket_service, customer_user))

        # Step 1: Apre ticket
        mock_ticket_service.create_ticket.return_value = {
            "id": 1, "session_id": 456, "status": "aperto",
        }
        client.post("/tickets", json={"session_id": 456})

        # Step 2: Invia messaggio come cliente
        mock_ticket_service.save_customer_message.return_value = {
            "id": 790, "sender": "user", "content": "Problema risolto",
        }

        msg_resp = client.post("/tickets/session/456/message", json={
            "content": "Problema risolto",
        })
        assert msg_resp.status_code == 200

        # Step 3: Chiude ticket dalla sessione
        mock_ticket_service.get_ticket_by_session.return_value = {
            "id": 1, "session_id": 456,
        }

        close_resp = client.patch("/tickets/session/456/close")
        assert close_resp.status_code == 200
