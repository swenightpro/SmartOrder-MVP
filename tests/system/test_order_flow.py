"""
Test di sistema: flusso completo di creazione ordine.
Verifica il percorso: ricerca prodotto → aggiungi al carrello → crea ordine.

NOTA: Marcati con @pytest.mark.system.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from controllers import cart_controller, order_controller
from controllers.cart_controller import _get_cart_service, _get_db_adapter
from controllers.order_controller import _get_order_service
from controllers.auth_controller import _get_current_user
from services.cart_service import CartService
from services.order_service import OrderService


@pytest.mark.system
class TestOrderFlow:
    """ST: Flusso completo di ordinazione"""

    @pytest.fixture
    def customer_user(self):
        return {"userId": 123, "cod_cli": 456, "role": "customer"}

    @pytest.fixture
    def mock_cart_service(self):
        return Mock(spec=CartService)

    @pytest.fixture
    def mock_order_service(self):
        return Mock(spec=OrderService)

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.get_active_session.return_value = {"id": 456}
        return db

    @pytest.fixture
    def app(self, mock_cart_service, mock_order_service, mock_db, customer_user):
        app = FastAPI()
        app.include_router(cart_controller.router)
        app.include_router(order_controller.router)
        app.dependency_overrides[_get_cart_service] = lambda: mock_cart_service
        app.dependency_overrides[_get_order_service] = lambda: mock_order_service
        app.dependency_overrides[_get_db_adapter] = lambda: mock_db
        app.dependency_overrides[_get_current_user] = lambda: customer_user
        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_add_to_cart_then_create_order(
        self, client, mock_cart_service, mock_order_service
    ):
        """ST: aggiungi prodotto → visualizza carrello → crea ordine"""
        # Step 1: Aggiungi al carrello
        mock_cart_service.add_to_cart.return_value = {
            "id": 1, "cod_art": "ART001", "qta": 5,
        }

        add_resp = client.post("/cart", json={
            "action": "add",
            "cod_art": "ART001",
            "qta": 5,
        })

        assert add_resp.status_code == 200
        assert add_resp.json()["success"] is True

        # Step 2: Visualizza carrello
        mock_cart_service.get_cart.return_value = [
            {"id": 1, "cod_art": "ART001", "qta": 5},
        ]

        cart_resp = client.get("/cart")

        assert cart_resp.status_code == 200
        assert len(cart_resp.json()) == 1

        # Step 3: Crea ordine
        mock_order_service.create_order.return_value = 789

        order_resp = client.post("/orders/create", json={
            "items": [{"cod_art": "ART001", "qta": 5}],
        })

        assert order_resp.status_code == 200
        assert order_resp.json()["order_id"] == 789

    def test_modify_cart_then_order(
        self, client, mock_cart_service, mock_order_service
    ):
        """ST: aggiungi → modifica quantità → crea ordine"""
        # Step 1: Aggiungi
        mock_cart_service.add_to_cart.return_value = {"id": 1, "cod_art": "ART001", "qta": 3}

        client.post("/cart", json={
            "action": "add",
            "cod_art": "ART001",
            "qta": 3,
        })

        # Step 2: Modifica quantità
        mock_cart_service.update_cart_quantity.return_value = True

        update_resp = client.post("/cart", json={
            "action": "update_quantity",
            "id": 1,
            "qta": 10,
        })

        assert update_resp.status_code == 200

        # Step 3: Crea ordine con quantità aggiornata
        mock_order_service.create_order.return_value = 790

        order_resp = client.post("/orders/create", json={
            "items": [{"cod_art": "ART001", "qta": 10}],
        })

        assert order_resp.status_code == 200
        assert order_resp.json()["order_id"] == 790

    def test_remove_from_cart_then_add_new_then_order(
        self, client, mock_cart_service, mock_order_service
    ):
        """ST: aggiungi → rimuovi → aggiungi altro → ordina"""
        # Step 1: Aggiungi primo prodotto
        mock_cart_service.add_to_cart.return_value = {"id": 1, "cod_art": "ART001", "qta": 2}
        client.post("/cart", json={"action": "add", "cod_art": "ART001", "qta": 2})

        # Step 2: Rimuovi primo prodotto
        mock_cart_service.remove_from_cart.return_value = True
        remove_resp = client.post("/cart", json={"action": "remove", "id": 1})
        assert remove_resp.status_code == 200

        # Step 3: Aggiungi secondo prodotto
        mock_cart_service.add_to_cart.return_value = {"id": 2, "cod_art": "ART002", "qta": 7}
        client.post("/cart", json={"action": "add", "cod_art": "ART002", "qta": 7})

        # Step 4: Crea ordine
        mock_order_service.create_order.return_value = 791
        order_resp = client.post("/orders/create", json={
            "items": [{"cod_art": "ART002", "qta": 7}],
        })

        assert order_resp.status_code == 200
        assert order_resp.json()["order_id"] == 791
