from __future__ import annotations

from unittest.mock import Mock

import pytest
from domain.models import Session

import adapters.postgres_adapter as pg
from adapters.postgres_adapter import PostgresAdapter


@pytest.fixture
def db():
    return PostgresAdapter()


@pytest.fixture
def stub_queries(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_execute_query(query: str, params=None, fetch=True):
        normalized = " ".join(query.split()).lower()
        calls.append(("many", normalized))

        if "from anacli" in normalized and "rag_soc ilike" in normalized:
            return [{"cod_cli": 10, "rag_soc": "ACME"}]
        if "from cart_items ci" in normalized and "where ci.session_id = %s" in normalized:
            return [{"id": 1, "cod_art": "A", "qta": 2}]
        if "delete from message_feedbacks" in normalized:
            return [{"id": 1}]
        if "delete from cart_items" in normalized:
            return [{"id": 1}]
        if "update cart_items" in normalized and "returning id" in normalized:
            return [{"id": 1}]
        if "from chat_messages cm" in normalized and "feedbacks" in normalized:
            return [
                {
                    "id": 1,
                    "session_id": 10,
                    "sender": "user",
                    "content": "x",
                    "metadata": "{}",
                    "image_data": b"abc",
                    "feedbacks": "[]",
                }
            ]
        if "from chat_messages cm" in normalized and "as feedback" in normalized:
            return [
                {
                    "id": 2,
                    "session_id": 10,
                    "sender": "ai",
                    "content": "ok",
                    "metadata": "{}",
                    "image_data": None,
                    "feedback": '{"is_positive": true}',
                }
            ]
        if "from chat_messages" in normalized and "where session_id = %s" in normalized:
            return [{"id": 1, "image_data": b"abc", "metadata": "{}", "created_at": "2026-01-01"}]
        if "from order_items oi" in normalized:
            return [{"id": 1, "cod_art": "A", "qta_ordinata": 2}]
        if "from orders o" in normalized and "json_agg" in normalized:
            return [{"order_id": 99, "data_ord": "2026-01-01"}]
        if "group by status" in normalized:
            return [{"status": "aperto", "count": 3}, {"status": "chiuso", "count": 1}]
        if "top_clients" in normalized or "from orders o left join anacli" in normalized:
            return [{"cod_cli": 10, "rag_soc": "ACME", "orders": 2}]
        if "generate_series" in normalized:
            return [{"day": "2026-01-01", "value": 1}]
        if "from anaart" in normalized:
            return [{"cod_art": "A", "des_art": "Acqua"}]
        if "from tickets" in normalized and "status in ('aperto', 'in_lavorazione')" in normalized:
            return [{"id": 1, "session_id": 10, "cod_cli": 10, "status": "aperto"}]
        if "update tickets" in normalized and "returning id, session_id" in normalized:
            return [{"id": 1, "session_id": 10}]
        return []

    def fake_execute_query_one(query: str, params=None):
        normalized = " ".join(query.split()).lower()
        calls.append(("one", normalized))

        if "from app_users" in normalized and "where lower(btrim(email))" in normalized:
            return {
                "id": 1,
                "email": "a@b.c",
                "password_hash": "hash",
                "password_salt": "salt",
                "role": "customer",
                "cod_cli": 10,
                "is_active": True,
                "created_at": "2026-01-01",
                "updated_at": "2026-01-01",
            }
        if "select id, email, password_hash, password_salt, role, cod_cli" in normalized and "from app_users where id = %s limit 1" in normalized:
            return {
                "id": 1,
                "email": "a@b.c",
                "password_hash": "hash",
                "password_salt": "salt",
                "role": "customer",
                "cod_cli": 10,
                "is_active": True,
                "created_at": "2026-01-01",
                "updated_at": "2026-01-01",
            }
        if "regexp_replace" in normalized:
            return {"seq_name": "orders_id_seq"}
        if "select cod_art from anaart" in normalized:
            return {"cod_art": "A"}
        if "insert into orders" in normalized and "returning id" in normalized:
            return {"id": 99}
        if "select id, qta from cart_items" in normalized:
            return {"id": 1, "qta": 2}
        if "insert into cart_items" in normalized:
            return {"id": 5, "cod_art": "A", "qta": 1}
        if "insert into chat_messages" in normalized and "returning id" in normalized:
            return {"id": 123}
        if "select id, cod_cli, user_id, session_id, data_ord from orders where id = %s and cod_cli = %s" in normalized:
            return {"id": 99, "cod_cli": 10, "session_id": 77, "data_ord": "2026-01-01"}
        if "select id, cod_cli, user_id, session_id, data_ord from orders where id = %s" in normalized:
            return {"id": 99, "cod_cli": 10, "session_id": 77, "data_ord": "2026-01-01"}
        if "select id from message_feedbacks" in normalized:
            return {"id": 7}
        if "update message_feedbacks" in normalized:
            return {"id": 7}
        if "insert into message_feedbacks" in normalized:
            return {"id": 8}
        if "select embedding from product_embeddings" in normalized:
            return {"embedding": [0.1, 0.2]}
        if "select 1 from product_embeddings" in normalized:
            return {"x": 1}
        if "select created_at from chat_messages" in normalized:
            return {"created_at": "2026-01-01"}
        if "select export_folder from app_users" in normalized:
            return {"export_folder": "C:/tmp"}
        if "select id, session_id, cod_cli, status, locked_by, created_at, updated_at from tickets where id = %s limit 1" in normalized:
            return {"id": 1, "session_id": 10, "cod_cli": 10, "status": "aperto"}
        if "insert into tickets" in normalized and "returning id, session_id, cod_cli, status, locked_by, created_at, updated_at" in normalized:
            return {"id": 1, "session_id": 10, "cod_cli": 10, "status": "aperto"}
        if "from tickets" in normalized and "where session_id = %s" in normalized:
            return {"id": 1, "session_id": 10, "cod_cli": 10, "status": "aperto"}
        if "select now()::text as generated_at" in normalized:
            return {"generated_at": "2026-01-01"}
        if "select" in normalized and "total_orders" in normalized and "total_tickets" in normalized:
            return {
                "total_orders": 1,
                "total_tickets": 2,
                "open_tickets": 1,
                "active_sessions": 1,
                "total_messages": 3,
            }
        return {"id": 1}

    monkeypatch.setattr(pg, "execute_query", fake_execute_query)
    monkeypatch.setattr(pg, "execute_query_one", fake_execute_query_one)
    return calls


def test_sequence_and_user_lookup_paths(db, stub_queries):
    db._resync_id_sequence("orders")
    db._resync_id_sequence("order_items")
    with pytest.raises(ValueError):
        db._resync_id_sequence("unknown")

    assert db.find_by_email("a@b.c")
    assert db.find_by_id(1)
    db.update_password(1, "hash", "salt")
    assert db.get_client_info(10)
    assert db.search_clients("acme")


def test_message_and_feedback_paths(db, stub_queries):
    msgs = db.get_messages(10)
    assert msgs[0]["image_data"]

    with_feedback = db.get_messages_with_feedback(10)
    assert isinstance(with_feedback[0]["feedbacks"], list)

    with_user_feedback = db.get_messages_with_user_feedback(10, 1)
    assert "feedback" in with_user_feedback[0]

    assert db.save_message(10, "user", "hello") == 123
    assert db.save_image_message(10, "user", "YWJj", "ocr") == 123
    assert db.get_message_by_id(1)


def test_cart_paths(db, stub_queries):
    db.get_active_session = Mock(return_value=Session(id=10, user_id=1, status="active"))
    db.create_session = Mock(return_value=Session(id=11, user_id=1, status="active"))

    assert db.get_cart(1)[0].cod_art == "A"
    db.get_active_session.return_value = None
    assert db.get_cart(1) == []

    db._validate_product_exists("A")
    with pytest.raises(ValueError):
        # Force product miss by patching helper at runtime.
        db._validate_product_exists = lambda cod_art: (_ for _ in ()).throw(ValueError("not found"))
        db._validate_product_exists("Z")

    db._validate_product_exists = Mock()
    db.get_active_session.return_value = Session(id=10, user_id=1, status="active")
    added = db.add_to_cart(1, "A", 1)
    assert added.id == 1

    assert db.add_to_cart_by_session(10, "A", 1)
    assert db.remove_from_cart_by_session(1, 10) is True
    assert db.update_cart_quantity_by_session(1, 10, 2) is True
    db.clear_cart_by_session(10)


def test_order_paths_and_helpers(db, stub_queries, monkeypatch):
    db.get_client_info = Mock(return_value={"cod_cli": 10})
    order_id = db.create_order(
        cod_cli=10,
        user_id=5,
        session_id=77,
        items=[{"cod_art": "A", "qta": 2, "source": "customer", "last_updated_by": "customer"}],
    )
    assert order_id == 99

    db.get_client_info = Mock(return_value=None)
    with pytest.raises(ValueError):
        db.create_order(10, 5, 77, [{"cod_art": "A", "qta": 2}])

    db.get_client_info = Mock(return_value={"cod_cli": 10})
    with pytest.raises(ValueError):
        db.create_order(10, 5, 77, [{"cod_art": "", "qta": 2}])

    where, params = db._build_order_conditions("o.cod_cli = %s", [10], "abc", "2026-01-01", "2026-01-31")
    assert "CAST(o.id AS TEXT) ILIKE" in where
    assert len(params) == 4

    assert db._safe_sort("id", "desc", ["id", "data_ord"]) == ("id", "DESC")
    assert db._safe_sort("hack", "asc", ["id", "data_ord"]) == ("data_ord", "ASC")

    assert db.get_orders_by_client(10)
    assert db.get_all_orders(search="abc", search_cod_cli="10", esportato=True)
    assert db.get_order_detail(99, 10)
    assert db.get_order_detail_any(99)


def test_product_feedback_embedding_and_ticket_paths(db, stub_queries):
    assert db.search_products("acqua", 10)
    assert db.find_product_by_name("acqua", 10)
    assert db.find_products_by_name_fuzzy("acqua", 10)

    original_has_embeddings = db.has_embeddings
    db.has_embeddings = Mock(return_value=False)
    assert db.find_product_by_name_merged("acqua", 10, [0.1])
    db.has_embeddings = original_has_embeddings

    found_code = db.find_product_by_code("A", 10)
    assert found_code and found_code["match_source"] == "code"

    assert db.save_feedback(1, 1, True) == 7
    assert db.delete_feedback(1, 1) is True

    assert db.search_products_for_ai("acqua", 10)
    assert db.search_products_keyword_no_asscli(["acqua"])
    assert db.search_products_keyword(["acque"], 10)
    assert db.get_embedding("A") == [0.1, 0.2]
    db.upsert_embedding("A", [0.1, 0.2])
    assert db.search_products_vector([0.1, 0.2], 10)
    assert db.has_embeddings() is True
    assert db.get_cart_by_client(10) == []
    assert db.get_cart_by_client(10, session_id=10)
    assert isinstance(db.get_order_history_flat(10), list)
    assert db.get_available_cod_art(10)
    assert db.get_last_orders(10)

    assert db.create_ticket(10, 10)
    assert db.get_ticket_by_session(10)
    assert db.get_open_tickets()
    overview = db.get_platform_usage_overview(14)
    assert overview["kpis"]["total_orders"] == 1
    assert db.get_ticket_by_id(1)
    assert db.lock_ticket(1, 2) is True
    db.unlock_ticket(1)
    db.close_ticket(1)
    db._save_system_message(10, "chiuso")
    assert db.get_last_message_time(10) == "2026-01-01"

    assert db.get_export_folder(1) == "C:/tmp"
    db.set_export_folder(1, "C:/tmp")
    db.mark_order_exported(1)
    db.mark_orders_exported([1, 2])
    assert db.send_message(10, "operator", "ciao") == 123
