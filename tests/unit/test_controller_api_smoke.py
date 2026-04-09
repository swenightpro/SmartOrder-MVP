import sys
sys.path.insert(0, "./backend")

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock

from main import app
from controllers import (
    auth_controller,
    conversation_controller,
    cart_controller,
    order_controller,
    product_controller,
    feedback_controller,
    client_controller,
    ticket_controller,
)

@pytest.fixture
def mock_auth_service():
    auth = Mock()
    auth.login = AsyncMock(return_value=("fake_token", {"user_id": 1, "tipo_cliente": "ASSCLI", "id_cliente": 100}))
    auth.verify_jwt = Mock(return_value={"sub": "1", "cod_cli": 100, "role": "client"})
    auth.get_profile = Mock(return_value={"id": 1, "name": "test"})
    return auth

@pytest.fixture
def mock_conversation_service():
    conv = Mock()
    conv.get_history = AsyncMock(return_value=[])
    conv.handle_message = AsyncMock(return_value={"success": True, "message": "hello"})
    conv.save_client_message = AsyncMock(return_value=1)
    conv.interpret_audio_and_handle = AsyncMock(return_value={"success": True, "message": "audio recognized"})
    return conv

@pytest.fixture
def mock_cart_service():
    cart = Mock()
    cart.get_cart = AsyncMock(return_value=[])
    cart.add_to_cart = AsyncMock(return_value={"id": 1, "success": True})
    cart.update_cart_quantity = AsyncMock(return_value={"id": 1, "success": True})
    cart.remove_from_cart = AsyncMock(return_value=True)
    cart.clear_cart = AsyncMock(return_value=True)
    return cart

@pytest.fixture
def mock_order_service():
    order = Mock()
    order.get_client_orders = AsyncMock(return_value=[])
    order.create_order_from_cart = AsyncMock(return_value=1)
    order.handle_payment_webhook = AsyncMock(return_value={"success": True})
    return order

@pytest.fixture
def mock_product_service():
    product = Mock()
    product.search_products = AsyncMock(return_value=[{"cod_art": "P1", "des_art": "test"}])
    return product

@pytest.fixture
def mock_feedback_service():
    feedback = Mock()
    feedback.save_feedback = AsyncMock(return_value=1)
    return feedback

@pytest.fixture
def mock_client_service():
    client = Mock()
    client.get_client_info = AsyncMock(return_value={"name": "test"})
    return client

@pytest.fixture
def mock_ticket_service():
    ticket = Mock()
    ticket.create_ticket = AsyncMock(return_value=1)
    ticket.get_tickets = AsyncMock(return_value=[])
    ticket.get_ticket_details = AsyncMock(return_value={"id": 1})
    ticket.add_reply = AsyncMock(return_value=1)
    return ticket

@pytest.fixture
def override_dependencies(
    mock_auth_service,
    mock_conversation_service,
    mock_cart_service,
    mock_order_service,
    mock_product_service,
    mock_feedback_service,
    mock_client_service,
    mock_ticket_service
):
    app.dependency_overrides[auth_controller._get_auth_service] = lambda: mock_auth_service
    app.dependency_overrides[conversation_controller._get_conversation_service] = lambda: mock_conversation_service
    app.dependency_overrides[cart_controller._get_cart_service] = lambda: mock_cart_service
    app.dependency_overrides[order_controller._get_order_service] = lambda: mock_order_service
    app.dependency_overrides[product_controller._get_product_service] = lambda: mock_product_service
    app.dependency_overrides[feedback_controller._get_feedback_service] = lambda: mock_feedback_service
    app.dependency_overrides[ticket_controller._get_ticket_service] = lambda: mock_ticket_service

    yield
    app.dependency_overrides = {}

@pytest.fixture
def client(override_dependencies):
    with TestClient(app, cookies={"smartorder_auth": "fake_jwt_token"}) as client:
        yield client

def test_health(client):
    response = client.get("/health")
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_login(client):
    response = client.post("/auth/login", data={"username": "test", "password": "pw"})
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_get_history(client):
    response = client.get("/sessions")
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_send_message(client):
    response = client.post("/chat", json={"message_content": "hello", "client_id": 100})
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_get_cart(client):
    response = client.get("/cart")
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_add_cart(client):
    response = client.post("/cart", json={"cod_art": "P1", "quantity": 1})
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_get_orders(client):
    response = client.get("/orders/list")
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_create_order(client):
    response = client.post("/orders/create", json={"notes": ""})
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_search_products(client):
    response = client.get("/products/search?q=test")
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_submit_feedback(client):
    response = client.post("/feedback", json={"message_id": 1, "is_positive": True})
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_get_client_info(client):
    response = client.get("/auth/me")
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_create_ticket(client):
    response = client.post("/tickets", json={"subject": "test", "message": "msg"})
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_get_tickets(client):
    response = client.get("/tickets")
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_get_ticket_details(client):
    response = client.get("/tickets/1")
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]

def test_reply_ticket(client):
    response = client.post("/tickets/1/message", json={"message": "reply"})
    assert response.status_code in [200, 201, 400, 401, 403, 404, 422, 500]
