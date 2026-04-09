from __future__ import annotations

import asyncio
import hashlib
import time
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from controllers import (
    auth_controller,
    cart_controller,
    client_controller,
    conversation_controller,
    feedback_controller,
    order_controller,
    product_controller,
    sse_controller,
    ticket_controller,
)
from domain.schemas import (
    AddByNameRequest,
    CartActionRequest,
    ChangePasswordRequest,
    ChatRequest,
    CloseTicketRequest,
    CreateOrderRequest,
    CreateTicketRequest,
    FeedbackRequest,
    LoginRequest,
    OrderItemRequest,
    SaveMessageRequest,
    SendMessageRequest,
)


class DummyRequest:
    def __init__(self, cookies: dict | None = None, query_params: dict | None = None):
        self.cookies = cookies or {}
        self.query_params = query_params or {}


class FakeUploadFile:
    def __init__(self, content: bytes, content_type: str, filename: str = "file.bin"):
        self._content = content
        self.content_type = content_type
        self.filename = filename
        self.file = BytesIO(content)

    async def read(self) -> bytes:
        return self._content


@pytest.fixture
def fake_settings():
    return SimpleNamespace(
        cookie_name="smartorder_auth",
        cookie_samesite="lax",
        cookie_secure=False,
        jwt_expiration_hours=24,
    )


def test_auth_current_user_happy_path(monkeypatch, fake_settings):
    svc = Mock()
    svc.verify_jwt.return_value = {"sub": "12", "cod_cli": 77, "role": "operator"}
    auth_controller._auth_svc = svc
    monkeypatch.setattr(auth_controller, "get_settings", lambda: fake_settings)

    user = auth_controller._get_current_user(DummyRequest(cookies={"smartorder_auth": "jwt"}))

    assert user == {"userId": 12, "cod_cli": 77, "role": "operator"}


def test_auth_current_user_missing_or_invalid_token(monkeypatch, fake_settings):
    svc = Mock()
    svc.verify_jwt.return_value = None
    auth_controller._auth_svc = svc
    monkeypatch.setattr(auth_controller, "get_settings", lambda: fake_settings)

    with pytest.raises(HTTPException) as missing:
        auth_controller._get_current_user(DummyRequest(cookies={}))
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as invalid:
        auth_controller._get_current_user(DummyRequest(cookies={"smartorder_auth": "bad"}))
    assert invalid.value.status_code == 401


def test_auth_controller_core_paths(monkeypatch, fake_settings):
    monkeypatch.setattr(auth_controller, "get_settings", lambda: fake_settings)
    svc = Mock()
    svc.login.return_value = {"token": "t", "cod_cli": 1, "rag_soc": "A", "role": "customer"}
    svc.get_profile.return_value = {"id": 1}
    svc.change_password.return_value = (True, "")

    response = Mock()
    out = auth_controller.login(LoginRequest(email="a@b.c", password="x"), response, svc)
    assert out["success"] is True
    response.set_cookie.assert_called_once()

    out_me = auth_controller.me({"userId": 1}, svc)
    assert out_me["user"]["id"] == 1

    cp = auth_controller.change_password(
        ChangePasswordRequest(
            current_password="old",
            new_password="new",
            confirm_new_password="new",
        ),
        {"userId": 1},
        svc,
    )
    assert cp == {"success": True}

    assert auth_controller.logout(Mock()) == {"success": True}


def test_auth_controller_error_and_admin_paths(monkeypatch, fake_settings):
    monkeypatch.setattr(auth_controller, "get_settings", lambda: fake_settings)
    svc = Mock()
    svc.login.return_value = None

    with pytest.raises(HTTPException) as login_err:
        auth_controller.login(LoginRequest(email="a@b.c", password="x"), Mock(), svc)
    assert login_err.value.status_code == 401

    svc.get_profile.return_value = None
    with pytest.raises(HTTPException) as me_err:
        auth_controller.me({"userId": 1}, svc)
    assert me_err.value.status_code == 404

    svc.change_password.return_value = (False, "La password attuale non è corretta")
    with pytest.raises(HTTPException) as cp_auth:
        auth_controller.change_password(
            ChangePasswordRequest(
                current_password="bad",
                new_password="new",
                confirm_new_password="new",
            ),
            {"userId": 1},
            svc,
        )
    assert cp_auth.value.status_code == 401

    svc.change_password.return_value = (False, "Le password non coincidono")
    with pytest.raises(HTTPException) as cp_bad:
        auth_controller.change_password(
            ChangePasswordRequest(
                current_password="old",
                new_password="new1",
                confirm_new_password="new2",
            ),
            {"userId": 1},
            svc,
        )
    assert cp_bad.value.status_code == 400

    with pytest.raises(HTTPException) as role_get:
        auth_controller.get_export_folder({"role": "customer", "userId": 1}, svc)
    assert role_get.value.status_code == 403

    with pytest.raises(HTTPException) as role_set:
        auth_controller.set_export_folder({"export_folder": "x"}, {"role": "customer", "userId": 1}, svc)
    assert role_set.value.status_code == 403

    svc.get_export_folder.return_value = "C:/tmp"
    assert auth_controller.get_export_folder({"role": "admin", "userId": 9}, svc) == {"export_folder": "C:/tmp"}
    assert auth_controller.set_export_folder({}, {"role": "admin", "userId": 9}, svc) == {"success": True}
    svc.set_export_folder.assert_called_once_with(9, None)

    with pytest.raises(HTTPException) as sse_missing:
        auth_controller.sse_token(DummyRequest(cookies={}))
    assert sse_missing.value.status_code == 401
    assert auth_controller.sse_token(DummyRequest(cookies={"smartorder_auth": "jwt"})) == {"token": "jwt"}


def test_cart_controller_all_branches():
    cart_svc = Mock()
    db = Mock()
    user_customer = {"userId": 7, "role": "customer"}
    user_operator = {"userId": 2, "role": "operator"}

    db.get_ticket_by_session.return_value = SimpleNamespace(status="in_lavorazione", locked_by=2)
    cart_controller._assert_session_access(12, user_operator, db)

    db.get_ticket_by_session.return_value = None
    with pytest.raises(HTTPException):
        cart_controller._assert_session_access(12, user_operator, db)

    db.get_ticket_by_session.return_value = SimpleNamespace(status="aperto", locked_by=2)
    with pytest.raises(HTTPException):
        cart_controller._assert_session_access(12, user_operator, db)

    db.get_ticket_by_session.return_value = SimpleNamespace(status="in_lavorazione", locked_by=99)
    with pytest.raises(HTTPException):
        cart_controller._assert_session_access(12, user_operator, db)

    db.get_active_session.return_value = None
    with pytest.raises(HTTPException):
        cart_controller._assert_session_access(3, user_customer, db)

    db.get_active_session.return_value = SimpleNamespace(id=3)
    cart_svc.get_cart.return_value = [{"id": 1}]
    assert cart_controller.get_cart(None, user_customer, cart_svc, db) == [{"id": 1}]

    cart_svc.get_cart_by_session.return_value = [{"id": 10}]
    assert cart_controller.get_cart(3, user_customer, cart_svc, db) == [{"id": 10}]

    with pytest.raises(HTTPException):
        cart_controller.cart_action(CartActionRequest(action="add", qta=1), user_customer, cart_svc, db)

    cart_svc.add_to_cart.side_effect = ValueError("bad")
    with pytest.raises(HTTPException):
        cart_controller.cart_action(CartActionRequest(action="add", cod_art="A", qta=1), user_customer, cart_svc, db)

    cart_svc.add_to_cart.side_effect = None
    cart_svc.add_to_cart.return_value = {"id": 1, "cod_art": "A", "qta": 1}
    added = cart_controller.cart_action(CartActionRequest(action="add", cod_art="A", qta=1), user_customer, cart_svc, db)
    assert added["success"] is True

    with pytest.raises(HTTPException):
        cart_controller.cart_action(CartActionRequest(action="remove"), user_customer, cart_svc, db)
    cart_svc.remove_from_cart.return_value = False
    with pytest.raises(HTTPException):
        cart_controller.cart_action(CartActionRequest(action="remove", id=1), user_customer, cart_svc, db)
    cart_svc.remove_from_cart.return_value = True
    assert cart_controller.cart_action(CartActionRequest(action="remove", id=1), user_customer, cart_svc, db) == {"success": True}

    with pytest.raises(HTTPException):
        cart_controller.cart_action(CartActionRequest(action="update_quantity", id=1), user_customer, cart_svc, db)
    cart_svc.update_cart_quantity.return_value = False
    with pytest.raises(HTTPException):
        cart_controller.cart_action(CartActionRequest(action="update_quantity", id=1, qta=2), user_customer, cart_svc, db)
    cart_svc.update_cart_quantity.return_value = True
    assert cart_controller.cart_action(CartActionRequest(action="update_quantity", id=1, qta=2), user_customer, cart_svc, db) == {"success": True}

    with pytest.raises(HTTPException):
        cart_controller.cart_action(CartActionRequest(action="invalid"), user_customer, cart_svc, db)

    db.find_product_by_name.return_value = None
    with pytest.raises(HTTPException):
        cart_controller.add_by_name(AddByNameRequest(product_name="acqua", qta=1), user_customer, cart_svc, db)

    db.find_product_by_name.return_value = {"cod_art": "A01"}
    cart_svc.add_to_cart.side_effect = ValueError("bad")
    with pytest.raises(HTTPException):
        cart_controller.add_by_name(AddByNameRequest(product_name="acqua", qta=1), user_customer, cart_svc, db)

    cart_svc.add_to_cart.side_effect = None
    cart_svc.add_to_cart.return_value = {"id": 100, "cod_art": "A01", "qta": 1}
    out = cart_controller.add_by_name(AddByNameRequest(product_name="acqua", qta=1), user_customer, cart_svc, db)
    assert out["success"] is True


def test_order_controller_branches():
    svc = Mock()
    customer = {"userId": 7, "cod_cli": 88, "role": "customer"}
    admin = {"userId": 1, "cod_cli": 0, "role": "admin"}

    with pytest.raises(HTTPException):
        order_controller._resolve_target_cod_cli(admin, None)
    assert order_controller._resolve_target_cod_cli(admin, 101) == 101

    with pytest.raises(HTTPException):
        order_controller._resolve_target_cod_cli({"userId": 7, "cod_cli": 0, "role": "customer"}, None)
    with pytest.raises(HTTPException):
        order_controller._resolve_target_cod_cli(customer, 999)
    assert order_controller._resolve_target_cod_cli(customer, None) == 88

    with pytest.raises(HTTPException):
        order_controller.create_order(CreateOrderRequest(items=[]), customer, svc)

    body = CreateOrderRequest(items=[OrderItemRequest(cod_art="A", qta=2)])
    svc.create_order.side_effect = ValueError("invalid")
    with pytest.raises(HTTPException):
        order_controller.create_order(body, customer, svc)

    svc.create_order.side_effect = None
    svc.create_order.return_value = 500
    assert order_controller.create_order(body, customer, svc) == {"order_id": 500}

    svc.get_orders_by_client.return_value = [{"order_id": 1}]
    out_default = order_controller.list_orders(user=customer, order_service=svc)
    assert out_default == [{"order_id": 1}]
    assert svc.get_orders_by_client.call_args[0][2] == 50
    out_filtered = order_controller.list_orders(search="x", user=customer, order_service=svc)
    assert out_filtered == [{"order_id": 1}]

    with pytest.raises(HTTPException):
        order_controller.list_all_orders(user=customer, order_service=svc)

    svc.get_all_orders.return_value = [{"order_id": 2}]
    all_orders = order_controller.list_all_orders(limit=999, user=admin, order_service=svc)
    assert all_orders == [{"order_id": 2}]
    assert svc.get_all_orders.call_args[0][1] == 100

    with pytest.raises(HTTPException):
        order_controller.export_batch_orders(user=customer, order_service=svc)

    svc.export_batch.side_effect = ValueError("bad")
    with pytest.raises(HTTPException):
        order_controller.export_batch_orders(user=admin, order_service=svc)
    svc.export_batch.side_effect = None
    svc.export_batch.return_value = {"ok": True}
    assert order_controller.export_batch_orders(user=admin, order_service=svc) == {"ok": True}

    svc.get_order_detail.return_value = None
    with pytest.raises(HTTPException):
        order_controller.order_detail(id=1, user=customer, order_service=svc)
    svc.get_order_detail.return_value = {"order_id": 1}
    assert order_controller.order_detail(id=1, user=customer, order_service=svc) == {"order_id": 1}

    with pytest.raises(HTTPException):
        order_controller.export_order(id=1, user=customer, order_service=svc)
    with pytest.raises(HTTPException):
        order_controller.export_order(id=1, format="xml", user=admin, order_service=svc)

    svc.export_order.side_effect = ValueError("bad")
    with pytest.raises(HTTPException):
        order_controller.export_order(id=1, format="json", user=admin, order_service=svc)

    svc.export_order.side_effect = None
    svc.export_order.return_value = None
    with pytest.raises(HTTPException):
        order_controller.export_order(id=1, format="json", user=admin, order_service=svc)

    svc.export_order.return_value = {"id": 1, "format": "json"}
    assert order_controller.export_order(id=1, format="json", user=admin, order_service=svc) == {"id": 1, "format": "json"}


@pytest.mark.asyncio
async def test_conversation_controller_standard_paths():
    conv = Mock()
    conv.handle_message = AsyncMock(return_value={"success": True})
    conv.transcribe_audio = AsyncMock(return_value="ciao")
    conv.get_active_session.return_value = SimpleNamespace(id=77)
    conv.create_session.return_value = SimpleNamespace(id=88)
    conv.get_messages_for_user.return_value = [{"id": 1}]
    conv.save_message_to_session.return_value = 100

    req = ChatRequest(message="ciao", clientId=1)
    out = await conversation_controller.chat(req, {"userId": 1}, conv)
    assert out == {"success": True}

    conv.handle_message.side_effect = RuntimeError("boom")
    with pytest.raises(HTTPException):
        await conversation_controller.chat(req, {"userId": 1}, conv)
    conv.handle_message.side_effect = None

    ok = await conversation_controller.save_message_to_session(
        SaveMessageRequest(session_id=1, sender="system", content="x"),
        {"userId": 1},
        conv,
    )
    assert ok == {"message_id": 100}

    with pytest.raises(HTTPException):
        await conversation_controller.save_message_to_session(
            SaveMessageRequest(session_id=1, sender="bad", content="x"),
            {"userId": 1},
            conv,
        )

    file_ok = FakeUploadFile(b"audio", "audio/webm", filename="audio.webm")
    assert await conversation_controller.transcribe(file_ok, conv) == {"text": "ciao"}
    conv.transcribe_audio.side_effect = RuntimeError("fail")
    with pytest.raises(HTTPException):
        await conversation_controller.transcribe(file_ok, conv)

    assert conversation_controller.get_active_session({"userId": 1}, conv) == {"session": {"id": 77}}
    conv.get_active_session.return_value = None
    assert conversation_controller.get_active_session({"userId": 1}, conv) == {"session": None}
    assert conversation_controller.create_session({"userId": 1}, conv) == {"session": {"id": 88}}
    assert conversation_controller.get_messages(session_id=2, user={"userId": 1}, conv_service=conv) == {"messages": [{"id": 1}]}


@pytest.mark.asyncio
async def test_conversation_controller_chat_image_branches():
    bad = FakeUploadFile(b"x", "text/plain")
    with pytest.raises(HTTPException) as bad_type:
        await conversation_controller.chat_image(bad, {"userId": 1, "cod_cli": 10}, Mock())
    assert bad_type.value.status_code == 400

    huge = FakeUploadFile(b"a" * (5 * 1024 * 1024 + 1), "image/png")
    with pytest.raises(HTTPException) as huge_type:
        await conversation_controller.chat_image(huge, {"userId": 1, "cod_cli": 10}, Mock())
    assert huge_type.value.status_code == 400

    dup_bytes = b"same"
    dup_hash = hashlib.sha256(dup_bytes).hexdigest()[:16]
    conversation_controller.chat_image._last_image_hash = dup_hash
    conversation_controller.chat_image._last_image_time = time.time()
    dup = FakeUploadFile(dup_bytes, "image/jpeg")
    dedup = await conversation_controller.chat_image(dup, {"userId": 1, "cod_cli": 10}, Mock())
    assert dedup["success"] is True
    assert "già elaborata" in dedup["response"]

    conv = Mock()
    conv.get_active_session.return_value = SimpleNamespace(id=9)
    conv.get_messages.return_value = []
    conv._ai_client = Mock()
    conv._ai_client.analyze_image = AsyncMock(return_value={"extracted_text": "", "products": []})
    conv._db = Mock()
    conv._db.save_image_message.return_value = 33
    conv._broadcaster = Mock()
    conv._broadcaster.emit = AsyncMock()

    no_text = await conversation_controller.chat_image(
        FakeUploadFile(b"img", "image/jpeg"),
        {"userId": 1, "cod_cli": 99},
        conv,
    )
    assert no_text["success"] is False
    assert no_text["user_message_id"] == 33

    conv2 = Mock()
    conv2.get_active_session.return_value = SimpleNamespace(id=11)
    conv2.get_messages.return_value = []
    conv2._ai_client = Mock()
    conv2._ai_client.analyze_image = AsyncMock(
        return_value={
            "extracted_text": "Acqua frizzante",
            "products": [{"name": "Acqua", "quantity": 2}],
        }
    )
    conv2._db = Mock()
    conv2._db.save_image_message.return_value = 44
    conv2._db.add_to_cart_by_session.return_value = {"id": 1}
    conv2._broadcaster = Mock()
    conv2._broadcaster.emit = AsyncMock()
    conv2.handle_message = AsyncMock(
        return_value={
            "response": "Aggiunto",
            "order_confirmed": True,
            "product_items": [{"cod_art": "A01", "quantity": 2}],
            "product_confidences": {"A01": 0.9},
            "ai_message_id": 77,
            "message": "Aggiunto",
            "cart_edits": [],
        }
    )

    out = await conversation_controller.chat_image(
        FakeUploadFile(b"img2", "image/jpeg"),
        {"userId": 1, "cod_cli": 99},
        conv2,
    )
    assert out["success"] is True
    assert out["ai_message_id"] == 77
    assert out["cart_synced"] is True


@pytest.mark.asyncio
async def test_ticket_controller_branches():
    svc = Mock()
    svc.get_open_tickets.return_value = [{"id": 1}]
    svc.create_ticket.return_value = {"id": 2}
    svc.get_ticket_by_session.return_value = {"id": 3, "cod_cli": 50}
    svc.get_platform_usage_overview.return_value = {"kpis": {}}
    svc.get_ticket_by_id.return_value = {"id": 10, "cod_cli": 50}
    svc.lock_ticket = AsyncMock(return_value=True)
    svc.send_chat_message = AsyncMock(return_value={"id": 99})
    svc.unlock_ticket = AsyncMock()
    svc.close_ticket = AsyncMock()
    svc.close_ticket_by_session = AsyncMock()
    svc.save_customer_message = AsyncMock(return_value={"id": 9})

    operator = {"userId": 1, "cod_cli": 0, "role": "admin"}
    customer = {"userId": 2, "cod_cli": 50, "role": "customer"}

    assert ticket_controller.list_open_tickets(operator, svc)["tickets"] == [{"id": 1}]
    assert ticket_controller.create_ticket(CreateTicketRequest(session_id=10), customer, svc)["ticket"]["id"] == 2
    assert ticket_controller.get_ticket_by_session(10, customer, svc)["ticket"]["id"] == 3
    assert ticket_controller.get_analytics_overview(14, operator, svc)["overview"] == {"kpis": {}}
    assert ticket_controller.get_ticket(10, operator, svc)["ticket"]["id"] == 10
    assert (await ticket_controller.lock_ticket(10, operator, svc))["success"] is True
    assert (await ticket_controller.send_ticket_message(10, SendMessageRequest(content="ok"), operator, svc))["message_id"] == 99
    assert (await ticket_controller.unlock_ticket(10, operator, svc))["success"] is True
    assert (await ticket_controller.close_ticket(10, CloseTicketRequest(closed_by="operator"), operator, svc))["success"] is True
    assert (await ticket_controller.close_ticket_by_session(10, None, customer, svc))["success"] is True
    assert (await ticket_controller.send_customer_message(10, SendMessageRequest(content="help"), customer, svc))["message_id"] == 9

    with pytest.raises(HTTPException):
        ticket_controller.list_open_tickets(customer, svc)

    svc.get_ticket_by_session.return_value = None
    with pytest.raises(HTTPException):
        ticket_controller.get_ticket_by_session(999, customer, svc)

    svc.get_ticket_by_id.return_value = None
    with pytest.raises(HTTPException):
        ticket_controller.get_ticket(999, operator, svc)

    svc.lock_ticket.return_value = False
    with pytest.raises(HTTPException):
        await ticket_controller.lock_ticket(10, operator, svc)

    svc.send_chat_message.side_effect = ValueError("bad")
    with pytest.raises(HTTPException):
        await ticket_controller.send_ticket_message(10, SendMessageRequest(content="x"), operator, svc)

    svc.get_ticket_by_id.return_value = {"id": 5, "cod_cli": 999}
    with pytest.raises(HTTPException):
        await ticket_controller.close_ticket(5, None, customer, svc)

    svc.get_ticket_by_session.return_value = None
    with pytest.raises(HTTPException):
        await ticket_controller.close_ticket_by_session(10, None, customer, svc)

    svc.save_customer_message.side_effect = ValueError("bad")
    with pytest.raises(HTTPException):
        await ticket_controller.send_customer_message(10, SendMessageRequest(content="x"), customer, svc)


def test_small_controllers_client_product_feedback():
    client_svc = Mock()
    client_svc.search_clients.return_value = [{"cod_cli": 1}]
    assert client_controller.search_clients("", client_svc) == []
    assert client_controller.search_clients(" ACME ", client_svc) == [{"cod_cli": 1}]

    product_svc = Mock()
    product_svc.search_products.return_value = [{"cod_art": "A"}]
    assert product_controller.search_products(" ", {"cod_cli": 1}, product_svc) == []
    assert product_controller.search_products("a", {"cod_cli": 1}, product_svc) == []
    assert product_controller.search_products("acqua", {"cod_cli": 1}, product_svc) == [{"cod_art": "A"}]

    feedback_svc = Mock()
    feedback_svc.save_feedback.return_value = 7
    assert feedback_controller.handle_feedback(
        FeedbackRequest(message_id=1, action="delete"),
        {"userId": 1},
        feedback_svc,
    ) == {"success": True, "deleted": True}

    with pytest.raises(HTTPException):
        feedback_controller.handle_feedback(
            FeedbackRequest(message_id=1, is_positive=None),
            {"userId": 1},
            feedback_svc,
        )

    out = feedback_controller.handle_feedback(
        FeedbackRequest(message_id=1, is_positive=True, comment="x" * 900),
        {"userId": 1},
        feedback_svc,
    )
    assert out == {"success": True, "id": 7}


def test_sse_controller_paths(monkeypatch, fake_settings):
    monkeypatch.setattr(sse_controller, "get_settings", lambda: fake_settings)

    auth = Mock()
    auth.verify_jwt.return_value = {"sub": "1", "cod_cli": 2, "role": "operator"}
    sse_controller._sse_auth_svc = auth

    user = sse_controller._get_current_user(DummyRequest(cookies={"smartorder_auth": "jwt"}))
    assert user["userId"] == 1

    auth.verify_jwt.return_value = None
    with pytest.raises(HTTPException):
        sse_controller._get_current_user(DummyRequest(cookies={"smartorder_auth": "bad"}))
    with pytest.raises(HTTPException):
        sse_controller._get_current_user(DummyRequest(cookies={}, query_params={}))

    auth.verify_jwt.return_value = {"sub": "9", "cod_cli": 3, "role": "operator"}
    q_user = sse_controller._get_current_user(DummyRequest(cookies={}, query_params={"token": "abc"}))
    assert q_user["userId"] == 9


@pytest.mark.asyncio
async def test_sse_endpoints_role_and_validation(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(sse_controller, "_event_stream", lambda request, channel_id, user: (sentinel, channel_id, user))

    with pytest.raises(HTTPException):
        await sse_controller.sse_tickets(DummyRequest(), {"role": "customer"})

    out = await sse_controller.sse_tickets(DummyRequest(), {"role": "operator", "userId": 1})
    assert out[0] is sentinel
    assert out[1] == sse_controller.OPERATOR_CHANNEL

    with pytest.raises(HTTPException):
        await sse_controller.sse_session(0, DummyRequest(), {"role": "operator", "userId": 1})

    out_session = await sse_controller.sse_session(123, DummyRequest(), {"role": "operator", "userId": 1})
    assert out_session[1] == 123


@pytest.mark.asyncio
async def test_sse_event_stream_internal_generator(monkeypatch):
    class FakeBroadcaster:
        def __init__(self):
            self.queue = asyncio.Queue()
            self.unsubscribed = False

        def _format_event(self, event, payload):
            return f"event: {event}\\ndata: {payload}\\n\\n"

        async def subscribe(self, channel_id):
            await self.queue.put("event: message\\ndata: {}\\n\\n")
            return self.queue

        async def unsubscribe(self, channel_id, queue):
            self.unsubscribed = True

    fake = FakeBroadcaster()
    monkeypatch.setattr(sse_controller, "get_broadcaster", lambda: fake)

    response = sse_controller._event_stream(DummyRequest(), 42, {"role": "operator"})
    first = await response.body_iterator.__anext__()
    second = await response.body_iterator.__anext__()
    assert "connected" in first
    assert "event: message" in second

    await response.body_iterator.aclose()
    assert fake.unsubscribed is True
