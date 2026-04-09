"""
Test di integrazione per auth_controller.
Verificano che i controller FastAPI interagiscano correttamente con i service.
Usano TestClient con dependency_overrides per iniettare mock dei servizi.
"""
import pytest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from controllers import auth_controller
from controllers.auth_controller import _get_auth_service, _get_current_user
from services.auth_service import AuthService


@pytest.fixture
def mock_auth_service():
    return Mock(spec=AuthService)


@pytest.fixture
def mock_user():
    return {"userId": 123, "cod_cli": 456, "role": "customer"}


@pytest.fixture
def mock_admin_user():
    return {"userId": 1, "cod_cli": 0, "role": "admin"}


@pytest.fixture
def app(mock_auth_service, mock_user):
    app = FastAPI()
    app.include_router(auth_controller.router)
    app.dependency_overrides[_get_auth_service] = lambda: mock_auth_service
    app.dependency_overrides[_get_current_user] = lambda: mock_user
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestAuthControllerLogin:
    """IT: POST /auth/login"""

    def test_login_success(self, mock_auth_service):
        """Test: login con credenziali valide ritorna 200 e setta cookie"""
        app = FastAPI()
        app.include_router(auth_controller.router)
        app.dependency_overrides[_get_auth_service] = lambda: mock_auth_service
        client = TestClient(app)

        mock_auth_service.login.return_value = {
            "token": "jwt_token_123",
            "cod_cli": 456,
            "rag_soc": "Test Company",
            "role": "customer",
        }

        resp = client.post("/auth/login", json={
            "email": "user@test.com",
            "password": "password123",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["user"]["cod_cli"] == 456
        assert data["user"]["role"] == "customer"

    def test_login_invalid_credentials(self, mock_auth_service):
        """Test: login con credenziali errate ritorna 401"""
        app = FastAPI()
        app.include_router(auth_controller.router)
        app.dependency_overrides[_get_auth_service] = lambda: mock_auth_service
        client = TestClient(app)

        mock_auth_service.login.return_value = None

        resp = client.post("/auth/login", json={
            "email": "user@test.com",
            "password": "wrong",
        })

        assert resp.status_code == 401

    def test_login_missing_fields(self, mock_auth_service):
        """Test: login senza campi obbligatori ritorna 422"""
        app = FastAPI()
        app.include_router(auth_controller.router)
        app.dependency_overrides[_get_auth_service] = lambda: mock_auth_service
        client = TestClient(app)

        resp = client.post("/auth/login", json={})

        assert resp.status_code == 422


class TestAuthControllerLogout:
    """IT: POST /auth/logout"""

    def test_logout_success(self, client):
        """Test: logout cancella il cookie e ritorna success"""
        resp = client.post("/auth/logout")

        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestAuthControllerMe:
    """IT: GET /auth/me"""

    def test_me_success(self, client, mock_auth_service):
        """Test: /me ritorna profilo utente autenticato"""
        mock_auth_service.get_profile.return_value = {
            "email": "user@test.com",
            "cod_cli": 456,
            "rag_soc": "Test Company",
            "role": "customer",
        }

        resp = client.get("/auth/me")

        assert resp.status_code == 200
        assert resp.json()["user"]["email"] == "user@test.com"

    def test_me_not_found(self, client, mock_auth_service):
        """Test: /me ritorna 404 se utente non trovato"""
        mock_auth_service.get_profile.return_value = None

        resp = client.get("/auth/me")

        assert resp.status_code == 404


class TestAuthControllerChangePassword:
    """IT: POST /auth/change-password"""

    def test_change_password_success(self, client, mock_auth_service):
        """Test: change-password con dati corretti ritorna success"""
        mock_auth_service.change_password.return_value = (True, "")

        resp = client.post("/auth/change-password", json={
            "current_password": "old_pass",
            "new_password": "new_pass_123",
            "confirm_new_password": "new_pass_123",
        })

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_change_password_wrong_current(self, client, mock_auth_service):
        """Test: change-password con password attuale sbagliata ritorna 401"""
        mock_auth_service.change_password.return_value = (
            False, "La password attuale non è corretta"
        )

        resp = client.post("/auth/change-password", json={
            "current_password": "wrong",
            "new_password": "new_pass_123",
            "confirm_new_password": "new_pass_123",
        })

        assert resp.status_code == 401

    def test_change_password_validation_error(self, client, mock_auth_service):
        """Test: change-password con validazione fallita ritorna 400"""
        mock_auth_service.change_password.return_value = (
            False, "Le nuove password non coincidono"
        )

        resp = client.post("/auth/change-password", json={
            "current_password": "old_pass",
            "new_password": "new1",
            "confirm_new_password": "new2",
        })

        assert resp.status_code == 400


class TestAuthControllerExportFolder:
    """IT: GET/PUT /auth/export-folder"""

    def test_get_export_folder_admin(self, mock_auth_service, mock_admin_user):
        """Test: operatore può leggere la sua export_folder"""
        app = FastAPI()
        app.include_router(auth_controller.router)
        app.dependency_overrides[_get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[_get_current_user] = lambda: mock_admin_user
        client = TestClient(app)

        mock_auth_service.get_export_folder.return_value = "/tmp/export"

        resp = client.get("/auth/export-folder")

        assert resp.status_code == 200
        assert resp.json()["export_folder"] == "/tmp/export"

    def test_get_export_folder_customer_forbidden(self, client):
        """Test: customer non può accedere a export-folder"""
        resp = client.get("/auth/export-folder")

        assert resp.status_code == 403

    def test_set_export_folder_admin(self, mock_auth_service, mock_admin_user):
        """Test: operatore può impostare export_folder"""
        app = FastAPI()
        app.include_router(auth_controller.router)
        app.dependency_overrides[_get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[_get_current_user] = lambda: mock_admin_user
        client = TestClient(app)

        resp = client.put("/auth/export-folder", json={
            "export_folder": "/new/path",
        })

        assert resp.status_code == 200
        mock_auth_service.set_export_folder.assert_called_once()
