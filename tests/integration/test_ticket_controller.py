"""
Test di integrazione per ticket_controller.
Verificano routing, autorizzazione e interazione controller-service.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from controllers import ticket_controller
from controllers.ticket_controller import _get_ticket_service
from controllers.auth_controller import _get_current_user
from services.ticket_service import TicketService


@pytest.fixture
def mock_ticket_service():
    svc = Mock(spec=TicketService)
    svc.lock_ticket = AsyncMock()
    svc.unlock_ticket = AsyncMock()
    svc.close_ticket = AsyncMock()
    svc.send_chat_message = AsyncMock()
    svc.close_ticket_by_session = AsyncMock()
    svc.save_customer_message = AsyncMock()
    return svc


@pytest.fixture
def operator_user():
    return {"userId": 1, "cod_cli": 0, "role": "admin"}


@pytest.fixture
def customer_user():
    return {"userId": 123, "cod_cli": 456, "role": "customer"}


def _make_app(mock_svc, user):
    app = FastAPI()
    app.include_router(ticket_controller.router)
    app.dependency_overrides[_get_ticket_service] = lambda: mock_svc
    app.dependency_overrides[_get_current_user] = lambda: user
    return app


class TestTicketControllerList:
    """IT: GET /tickets"""

    def test_list_tickets_operator(self, mock_ticket_service, operator_user):
        """Test: operatore vede lista ticket aperti"""
        client = TestClient(_make_app(mock_ticket_service, operator_user))
        mock_ticket_service.get_open_tickets.return_value = [
            {"id": 1, "status": "aperto"},
        ]

        resp = client.get("/tickets")

        assert resp.status_code == 200
        assert len(resp.json()["tickets"]) == 1

    def test_list_tickets_customer_forbidden(self, mock_ticket_service, customer_user):
        """Test: customer non può vedere lista ticket operatore"""
        client = TestClient(_make_app(mock_ticket_service, customer_user))

        resp = client.get("/tickets")

        assert resp.status_code == 403


class TestTicketControllerCreate:
    """IT: POST /tickets"""

    def test_create_ticket_success(self, mock_ticket_service, customer_user):
        """Test: cliente crea un ticket"""
        client = TestClient(_make_app(mock_ticket_service, customer_user))
        mock_ticket_service.create_ticket.return_value = {
            "id": 1, "session_id": 456, "status": "aperto",
        }

        resp = client.post("/tickets", json={"session_id": 456})

        assert resp.status_code == 200
        assert resp.json()["ticket"]["status"] == "aperto"


class TestTicketControllerGetById:
    """IT: GET /tickets/{id}"""

    def test_get_ticket_operator(self, mock_ticket_service, operator_user):
        """Test: operatore vede dettaglio ticket"""
        client = TestClient(_make_app(mock_ticket_service, operator_user))
        mock_ticket_service.get_ticket_by_id.return_value = {
            "id": 1, "session_id": 456,
        }

        resp = client.get("/tickets/1")

        assert resp.status_code == 200

    def test_get_ticket_not_found(self, mock_ticket_service, operator_user):
        """Test: ticket non trovato ritorna 404"""
        client = TestClient(_make_app(mock_ticket_service, operator_user))
        mock_ticket_service.get_ticket_by_id.return_value = None

        resp = client.get("/tickets/999")

        assert resp.status_code == 404


class TestTicketControllerLock:
    """IT: PATCH /tickets/{id}/lock"""

    def test_lock_ticket_success(self, mock_ticket_service, operator_user):
        """Test: operatore locka un ticket"""
        client = TestClient(_make_app(mock_ticket_service, operator_user))
        mock_ticket_service.lock_ticket.return_value = True

        resp = client.patch("/tickets/1/lock")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_lock_ticket_conflict(self, mock_ticket_service, operator_user):
        """Test: lock su ticket già lockato ritorna 409"""
        client = TestClient(_make_app(mock_ticket_service, operator_user))
        mock_ticket_service.lock_ticket.return_value = False

        resp = client.patch("/tickets/1/lock")

        assert resp.status_code == 409

    def test_lock_ticket_customer_forbidden(self, mock_ticket_service, customer_user):
        """Test: customer non può lockare ticket"""
        client = TestClient(_make_app(mock_ticket_service, customer_user))

        resp = client.patch("/tickets/1/lock")

        assert resp.status_code == 403


class TestTicketControllerUnlock:
    """IT: PATCH /tickets/{id}/unlock"""

    def test_unlock_ticket_success(self, mock_ticket_service, operator_user):
        """Test: operatore rilascia lock"""
        client = TestClient(_make_app(mock_ticket_service, operator_user))

        resp = client.patch("/tickets/1/unlock")

        assert resp.status_code == 200
        mock_ticket_service.unlock_ticket.assert_called_once()


class TestTicketControllerClose:
    """IT: PATCH /tickets/{id}/close"""

    def test_close_ticket_operator(self, mock_ticket_service, operator_user):
        """Test: operatore chiude un ticket"""
        client = TestClient(_make_app(mock_ticket_service, operator_user))
        mock_ticket_service.get_ticket_by_id.return_value = {
            "id": 1, "session_id": 456, "cod_cli": 100,
        }

        resp = client.patch("/tickets/1/close")

        assert resp.status_code == 200
        mock_ticket_service.close_ticket.assert_called_once()

    def test_close_ticket_not_found(self, mock_ticket_service, operator_user):
        """Test: chiusura ticket inesistente ritorna 404"""
        client = TestClient(_make_app(mock_ticket_service, operator_user))
        mock_ticket_service.get_ticket_by_id.return_value = None

        resp = client.patch("/tickets/999/close")

        assert resp.status_code == 404


class TestTicketControllerSendMessage:
    """IT: POST /tickets/{id}/message"""

    def test_send_message_operator(self, mock_ticket_service, operator_user):
        """Test: operatore invia messaggio in chat ticket"""
        client = TestClient(_make_app(mock_ticket_service, operator_user))
        mock_ticket_service.send_chat_message.return_value = {
            "id": 789, "sender": "operator", "content": "Ti aiuto",
        }

        resp = client.post("/tickets/1/message", json={"content": "Ti aiuto"})

        assert resp.status_code == 200
        assert resp.json()["message_id"] == 789

    def test_send_message_customer_forbidden(self, mock_ticket_service, customer_user):
        """Test: customer non può usare endpoint operatore"""
        client = TestClient(_make_app(mock_ticket_service, customer_user))

        resp = client.post("/tickets/1/message", json={"content": "test"})

        assert resp.status_code == 403


class TestTicketControllerBySession:
    """IT: endpoint /tickets/session/{session_id}"""

    def test_get_ticket_by_session(self, mock_ticket_service, customer_user):
        """Test: cliente vede ticket della propria sessione"""
        client = TestClient(_make_app(mock_ticket_service, customer_user))
        mock_ticket_service.get_ticket_by_session.return_value = {
            "id": 1, "session_id": 456, "status": "aperto",
        }

        resp = client.get("/tickets/session/456")

        assert resp.status_code == 200

    def test_get_ticket_by_session_not_found(self, mock_ticket_service, customer_user):
        """Test: nessun ticket per sessione ritorna 404"""
        client = TestClient(_make_app(mock_ticket_service, customer_user))
        mock_ticket_service.get_ticket_by_session.return_value = None

        resp = client.get("/tickets/session/999")

        assert resp.status_code == 404

    def test_close_ticket_by_session(self, mock_ticket_service, customer_user):
        """Test: cliente chiude ticket della propria sessione"""
        client = TestClient(_make_app(mock_ticket_service, customer_user))
        mock_ticket_service.get_ticket_by_session.return_value = {
            "id": 1, "session_id": 456,
        }

        resp = client.patch("/tickets/session/456/close")

        assert resp.status_code == 200

    def test_send_customer_message(self, mock_ticket_service, customer_user):
        """Test: cliente invia messaggio nella chat ticket"""
        client = TestClient(_make_app(mock_ticket_service, customer_user))
        mock_ticket_service.save_customer_message.return_value = {
            "id": 789, "sender": "user", "content": "Aiuto!",
        }

        resp = client.post("/tickets/session/456/message", json={
            "content": "Aiuto!",
        })

        assert resp.status_code == 200
        assert resp.json()["message_id"] == 789
