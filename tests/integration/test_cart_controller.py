"""
Test di integrazione per cart_controller.
Verificano routing, autorizzazione e interazione controller-service.
"""
import pytest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from controllers import cart_controller
from controllers.cart_controller import _get_cart_service, _get_db_adapter
from controllers.auth_controller import _get_current_user
from services.cart_service import CartService


@pytest.fixture
def mock_cart_service():
    return Mock(spec=CartService)


@pytest.fixture
def mock_db():
    db = Mock()
    session = Mock()
    session.id = 456
    db.get_active_session.return_value = session
    return db


@pytest.fixture
def customer_user():
    return {"userId": 123, "cod_cli": 456, "role": "customer"}


@pytest.fixture
def app(mock_cart_service, mock_db, customer_user):
    app = FastAPI()
    app.include_router(cart_controller.router)
    app.dependency_overrides[_get_cart_service] = lambda: mock_cart_service
    app.dependency_overrides[_get_db_adapter] = lambda: mock_db
    app.dependency_overrides[_get_current_user] = lambda: customer_user
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestCartControllerGet:
    """IT: GET /cart"""

    def test_get_cart_by_user(self, client, mock_cart_service):
        """Test: get cart senza session_id usa user_id"""
        mock_cart_service.get_cart.return_value = [
            {"id": 1, "cod_art": "ART001", "qta": 5},
        ]

        resp = client.get("/cart")

        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_cart_by_session(self, client, mock_cart_service, mock_db):
        """Test: get cart con session_id valida"""
        mock_cart_service.get_cart_by_session.return_value = [
            {"id": 1, "cod_art": "ART001", "qta": 2},
        ]

        resp = client.get("/cart", params={"session_id": 456})

        assert resp.status_code == 200


class TestCartControllerActions:
    """IT: POST /cart"""

    def test_add_to_cart(self, client, mock_cart_service):
        """Test: aggiunta articolo al carrello"""
        mock_cart_service.add_to_cart.return_value = {
            "id": 1, "cod_art": "ART001", "qta": 5,
        }

        resp = client.post("/cart", json={
            "action": "add",
            "cod_art": "ART001",
            "qta": 5,
        })

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_add_to_cart_missing_fields(self, client):
        """Test: add senza cod_art/qta ritorna 400"""
        resp = client.post("/cart", json={
            "action": "add",
        })

        assert resp.status_code == 400

    def test_remove_from_cart(self, client, mock_cart_service):
        """Test: rimozione articolo dal carrello"""
        mock_cart_service.remove_from_cart.return_value = True

        resp = client.post("/cart", json={
            "action": "remove",
            "id": 1,
        })

        assert resp.status_code == 200

    def test_remove_from_cart_not_found(self, client, mock_cart_service):
        """Test: rimozione articolo non trovato ritorna 404"""
        mock_cart_service.remove_from_cart.return_value = False

        resp = client.post("/cart", json={
            "action": "remove",
            "id": 999,
        })

        assert resp.status_code == 404

    def test_update_quantity(self, client, mock_cart_service):
        """Test: aggiornamento quantità articolo"""
        mock_cart_service.update_cart_quantity.return_value = True

        resp = client.post("/cart", json={
            "action": "update_quantity",
            "id": 1,
            "qta": 10,
        })

        assert resp.status_code == 200

    def test_invalid_action(self, client):
        """Test: azione non valida ritorna 400"""
        resp = client.post("/cart", json={
            "action": "invalid_action",
        })

        assert resp.status_code == 400
