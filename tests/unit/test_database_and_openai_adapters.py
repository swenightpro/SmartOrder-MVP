from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import adapters.database as db_mod
import adapters.openai_adapter as oa_mod


class _FakeCursor:
    def __init__(self, rows=None, has_description=True, should_fail=False):
        self._rows = rows or []
        self.description = ["col"] if has_description else None
        self._should_fail = should_fail
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def execute(self, query, params):
        self.executed.append((query, params))
        if self._should_fail:
            raise RuntimeError("sql error")

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor
        self.closed = False
        self.committed = 0
        self.rolled_back = 0

    def cursor(self, cursor_factory=None):
        return self._cursor

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self._conn = conn
        self.closed = False
        self.put_count = 0

    def getconn(self):
        return self._conn

    def putconn(self, conn):
        self.put_count += 1

    def closeall(self):
        self.closed = True


def test_database_pool_and_query_paths(monkeypatch):
    settings = SimpleNamespace(
        db_host="localhost",
        db_port=5432,
        db_user="u",
        db_password="p",
        db_name="n",
    )
    monkeypatch.setattr(db_mod, "get_settings", lambda: settings)

    created = {}

    def fake_pool_ctor(**kwargs):
        created["kwargs"] = kwargs
        return _FakePool(_FakeConn(_FakeCursor(rows=[{"x": 1}])))

    monkeypatch.setattr(db_mod.pool, "SimpleConnectionPool", fake_pool_ctor)
    db_mod._pool = None

    p1 = db_mod.get_pool()
    p2 = db_mod.get_pool()
    assert p1 is p2
    assert created["kwargs"]["host"] == "localhost"

    rows = db_mod.execute_query("SELECT 1", params=(1,), fetch=True)
    assert rows == [{"x": 1}]

    no_rows = db_mod.execute_query("UPDATE x", params=(), fetch=False)
    assert no_rows == []

    one = db_mod.execute_query_one("SELECT 1")
    assert one == {"x": 1}

    db_mod.close_pool()
    assert db_mod._pool is None


def test_database_query_error_rolls_back_and_releases(monkeypatch):
    failing_cursor = _FakeCursor(should_fail=True)
    conn = _FakeConn(failing_cursor)
    pool = _FakePool(conn)
    monkeypatch.setattr(db_mod, "get_pool", lambda: pool)

    with pytest.raises(RuntimeError):
        db_mod.execute_query("SELECT fail", params=None, fetch=True)

    assert conn.rolled_back == 1
    assert pool.put_count == 1


@pytest.fixture
def openai_adapter(monkeypatch):
    settings = SimpleNamespace(
        openai_api_key="key",
        ai_model="smart-model",
        whisper_model="whisper-model",
        embedding_model="embed-model",
    )
    monkeypatch.setattr(oa_mod, "get_settings", lambda: settings)

    mock_client = Mock()
    monkeypatch.setattr(oa_mod, "OpenAI", Mock(return_value=mock_client))

    adapter = oa_mod.OpenAIAdapter()
    return adapter, mock_client


@pytest.mark.asyncio
async def test_openai_adapter_transcribe_and_intent(openai_adapter):
    adapter, client = openai_adapter

    transcript = SimpleNamespace(text="trascritto")
    client.audio.transcriptions.create.return_value = transcript

    out = await adapter.transcribe_audio(BytesIO(b"abc"), "audio.wav")
    assert out == "trascritto"

    chat_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"intent":"ORDER"}'))]
    )
    client.chat.completions.create.return_value = chat_resp

    intent = await adapter.interpret_intent("ciao", "ctx", "sys")
    assert "ORDER" in intent


def test_openai_adapter_embedding(openai_adapter):
    adapter, client = openai_adapter
    emb = SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])
    client.embeddings.create.return_value = emb

    out = adapter.generate_embedding("acqua")
    assert out == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_openai_adapter_analyze_image(openai_adapter):
    adapter, client = openai_adapter

    parsed = SimpleNamespace(
        extracted_text="acqua frizzante",
        ai_response="ok",
        products=[SimpleNamespace(name="Acqua", quantity=2, confidence=0.9)],
    )
    resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))])
    client.beta.chat.completions.parse.return_value = resp

    out = await adapter.analyze_image(
        image_base64="YWJj",
        conversation_history=[{"role": "user", "content": "ciao"}],
        system_prompt="sys",
    )

    assert out["extracted_text"] == "acqua frizzante"
    assert out["products"][0]["name"] == "Acqua"