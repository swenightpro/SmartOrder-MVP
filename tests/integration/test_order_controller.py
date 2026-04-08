"""
Test di integrazione per order_controller.
Verificano routing, autorizzazione e interazione controller-service.
"""
import pytest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from controllers import order_controller
from controllers.order_controller import _get_order_service
from controllers.auth_controller import _get_current_user
from services.order_service import OrderService


@pytest.fixture
def mock_order_service():
    return Mock(spec=OrderService)


@pytest.fixture
def customer_user():
    return {"userId": 123, "cod_cli": 456, "role": "customer"}


@pytest.fixture
def admin_user():
    return {"userId": 1, "cod_cli": 0, "role": "admin"}


def _make_app(mock_svc, user):
    app = FastAPI()
    app.include_router(order_controller.router)
    app.dependency_overrides[_get_order_service] = lambda: mock_svc
    app.dependency_overrides[_get_current_user] = lambda: user
    return app


class TestOrderControllerCreate:
    """IT: POST /orders/create"""

    def test_create_order_success(self, mock_order_service, customer_user):
        """Test: creazione ordine con articoli validi"""
        client = TestClient(_make_app(mock_order_service, customer_user))
        mock_order_service.create_order.return_value = 789

        resp = client.post("/orders/create", json={
            "items": [{"cod_art": "ART001", "qta": 5}],
            "session_id": 456,
        })

        assert resp.status_code == 200
        assert resp.json()["order_id"] == 789

    def test_create_order_empty_items(self, mock_order_service, customer_user):
        """Test: creazione ordine senza articoli ritorna 400"""
        client = TestClient(_make_app(mock_order_service, customer_user))

        resp = client.post("/orders/create", json={"items": []})

        assert resp.status_code == 400

    def test_create_order_admin_requires_cod_cli(self, mock_order_service, admin_user):
        """Test: admin senza cod_cli ritorna 400"""
        client = TestClient(_make_app(mock_order_service, admin_user))

        resp = client.post("/orders/create", json={
            "items": [{"cod_art": "ART001", "qta": 1}],
        })

        assert resp.status_code == 400


class TestOrderControllerList:
    """IT: GET /orders/list"""

    def test_list_orders_customer(self, mock_order_service, customer_user):
        """Test: customer vede i propri ordini"""
        client = TestClient(_make_app(mock_order_service, customer_user))
        mock_order_service.get_orders_by_client.return_value = [
            {"id": 1, "data_ord": "2026-04-01"},
        ]

        resp = client.get("/orders/list")

        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_orders_with_filters(self, mock_order_service, customer_user):
        """Test: filtri data e ricerca passati al service"""
        client = TestClient(_make_app(mock_order_service, customer_user))
        mock_order_service.get_orders_by_client.return_value = []

        resp = client.get("/orders/list", params={
            "search": "pasta",
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
        })

        assert resp.status_code == 200


class TestOrderControllerAll:
    """IT: GET /orders/all"""

    def test_all_orders_admin_only(self, mock_order_service, customer_user):
        """Test: customer non può accedere a /orders/all"""
        client = TestClient(_make_app(mock_order_service, customer_user))

        resp = client.get("/orders/all")

        assert resp.status_code == 403

    def test_all_orders_admin(self, mock_order_service, admin_user):
        """Test: admin vede tutti gli ordini"""
        client = TestClient(_make_app(mock_order_service, admin_user))
        mock_order_service.get_all_orders.return_value = [
            {"id": 1}, {"id": 2},
        ]

        resp = client.get("/orders/all")

        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestOrderControllerDetail:
    """IT: GET /orders/detail"""

    def test_order_detail_success(self, mock_order_service, customer_user):
        """Test: dettaglio ordine ritorna i dati"""
        client = TestClient(_make_app(mock_order_service, customer_user))
        mock_order_service.get_order_detail.return_value = {
            "id": 1, "items": [],
        }

        resp = client.get("/orders/detail", params={"id": 1})

        assert resp.status_code == 200

    def test_order_detail_not_found(self, mock_order_service, customer_user):
        """Test: dettaglio ordine inesistente ritorna 404"""
        client = TestClient(_make_app(mock_order_service, customer_user))
        mock_order_service.get_order_detail.return_value = None

        resp = client.get("/orders/detail", params={"id": 999})

        assert resp.status_code == 404


class TestOrderControllerExport:
    """IT: POST /orders/export"""

    def test_export_order_admin(self, mock_order_service, admin_user):
        """Test: admin può esportare un ordine"""
        client = TestClient(_make_app(mock_order_service, admin_user))
        mock_order_service.export_order.return_value = {
            "file_path": "/tmp/ordine_1.json",
            "filename": "ordine_1.json",
            "format": "json",
        }

        resp = client.post("/orders/export", params={"id": 1, "format": "json"})

        assert resp.status_code == 200
        assert resp.json()["format"] == "json"

    def test_export_order_customer_forbidden(self, mock_order_service, customer_user):
        """Test: customer non può esportare ordini"""
        client = TestClient(_make_app(mock_order_service, customer_user))

        resp = client.post("/orders/export", params={"id": 1})

        assert resp.status_code == 403

    def test_export_order_invalid_format(self, mock_order_service, admin_user):
        """Test: formato non supportato ritorna 400"""
        client = TestClient(_make_app(mock_order_service, admin_user))

        resp = client.post("/orders/export", params={"id": 1, "format": "xml"})

        assert resp.status_code == 400


class TestOrderControllerExportBatch:
    """IT: POST /orders/export-batch"""

    def test_export_batch_admin(self, mock_order_service, admin_user):
        """Test: admin può esportare in batch"""
        client = TestClient(_make_app(mock_order_service, admin_user))
        mock_order_service.export_batch.return_value = {
            "exported_count": 5,
            "failed_count": 0,
            "errors": [],
        }

        resp = client.post("/orders/export-batch")

        assert resp.status_code == 200
        assert resp.json()["exported_count"] == 5

    def test_export_batch_customer_forbidden(self, mock_order_service, customer_user):
        """Test: customer non può esportare in batch"""
        client = TestClient(_make_app(mock_order_service, customer_user))

        resp = client.post("/orders/export-batch")

        assert resp.status_code == 403
