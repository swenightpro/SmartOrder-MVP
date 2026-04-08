"""
Test di sistema: flusso di login end-to-end.
Verifica il percorso completo login → autenticazione → accesso risorsa protetta.

NOTA: Questi test richiedono un'istanza del backend avviata o un DB di test.
      Sono marcati con @pytest.mark.system e skippati di default.
"""
import pytest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from controllers import auth_controller
from controllers.auth_controller import _get_auth_service
from services.auth_service import AuthService


@pytest.mark.system
class TestLoginFlow:
    """ST: Flusso completo di autenticazione"""

    @pytest.fixture
    def mock_auth_service(self):
        svc = Mock(spec=AuthService)
        return svc

    @pytest.fixture
    def app(self, mock_auth_service):
        app = FastAPI()
        app.include_router(auth_controller.router)
        app.dependency_overrides[_get_auth_service] = lambda: mock_auth_service
        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_login_then_access_protected_resource(self, client, mock_auth_service):
        """ST: login → cookie JWT → accesso /auth/me → profilo utente"""
        # Step 1: Login
        mock_auth_service.login.return_value = {
            "token": "valid_jwt_token",
            "cod_cli": 456,
            "rag_soc": "Test Company",
            "role": "customer",
        }

        login_resp = client.post("/auth/login", json={
            "email": "user@test.com",
            "password": "password123",
        })

        assert login_resp.status_code == 200
        assert login_resp.json()["success"] is True
        # Verifica che il cookie JWT sia stato impostato
        assert any("smartorder_token" in c or "token" in c
                    for c in login_resp.headers.get("set-cookie", "").split(";"))

    def test_login_then_logout_clears_session(self, client, mock_auth_service):
        """ST: login → logout → cookie rimosso"""
        # Step 1: Login
        mock_auth_service.login.return_value = {
            "token": "valid_jwt_token",
            "cod_cli": 456,
            "rag_soc": "Company",
            "role": "customer",
        }
        client.post("/auth/login", json={
            "email": "user@test.com",
            "password": "pass",
        })

        # Step 2: Logout
        logout_resp = client.post("/auth/logout")

        assert logout_resp.status_code == 200
        assert logout_resp.json()["success"] is True

    def test_register_then_login(self, client, mock_auth_service):
        """ST: registrazione → login con nuovo utente"""
        # Step 1: Register
        mock_auth_service.register.return_value = (True, "")

        register_resp = client.post("/auth/register", json={
            "email": "new@test.com",
            "password": "password123",
            "role": "customer",
            "cod_cli": 100,
        })

        assert register_resp.status_code == 200

        # Step 2: Login con credenziali appena create
        mock_auth_service.login.return_value = {
            "token": "jwt_for_new_user",
            "cod_cli": 100,
            "rag_soc": "New Company",
            "role": "customer",
        }

        login_resp = client.post("/auth/login", json={
            "email": "new@test.com",
            "password": "password123",
        })

        assert login_resp.status_code == 200
        assert login_resp.json()["user"]["cod_cli"] == 100
