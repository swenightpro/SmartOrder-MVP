import pytest
import asyncio
import json
from services.sse_broadcaster import SSEBroadcaster, get_broadcaster


class TestSSEBroadcaster:
    """Unit test per SSEBroadcaster (Server-Sent Events)"""

    @pytest.fixture
    async def broadcaster(self):
        """Istanza di SSEBroadcaster per ogni test"""
        return SSEBroadcaster()

    # ========== Test Subscribe ==========

    @pytest.mark.asyncio
    async def test_subscribe_returns_queue(self):
        """Test: subscribe() ritorna una asyncio.Queue"""
        # Setup
        broadcaster = SSEBroadcaster()
        session_id = 456
        
        # Execute
        queue = await broadcaster.subscribe(session_id)
        
        # Verify
        assert isinstance(queue, asyncio.Queue)

    @pytest.mark.asyncio
    async def test_subscribe_creates_multiple_queues(self):
        """Test: stessa sessione può avere più subscriber"""
        # Setup
        broadcaster = SSEBroadcaster()
        session_id = 456
        
        # Execute
        queue1 = await broadcaster.subscribe(session_id)
        queue2 = await broadcaster.subscribe(session_id)
        
        # Verify - sono due queue diverse
        assert queue1 is not queue2

    @pytest.mark.asyncio
    async def test_subscribe_different_sessions(self):
        """Test: session diverse hanno subscriber separati"""
        # Setup
        broadcaster = SSEBroadcaster()
        
        # Execute
        queue1 = await broadcaster.subscribe(456)
        queue2 = await broadcaster.subscribe(789)
        
        # Verify - Queue diverse per session diverse
        assert queue1 is not queue2

    # ========== Test Unsubscribe ==========

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_queue(self):
        """Test: unsubscribe() rimuove subscriber"""
        # Setup
        broadcaster = SSEBroadcaster()
        session_id = 456
        queue = await broadcaster.subscribe(session_id)
        
        # Verify - è iscritto
        assert session_id in broadcaster._subscribers
        
        # Execute
        await broadcaster.unsubscribe(session_id, queue)
        
        # Verify - non è più iscritto
        assert session_id not in broadcaster._subscribers

    @pytest.mark.asyncio
    async def test_unsubscribe_keeps_other_subscribers(self):
        """Test: unsubscribe() rimuove solo il subscriber specificato"""
        # Setup
        broadcaster = SSEBroadcaster()
        session_id = 456
        queue1 = await broadcaster.subscribe(session_id)
        queue2 = await broadcaster.subscribe(session_id)
        
        # Execute
        await broadcaster.unsubscribe(session_id, queue1)
        
        # Verify - queue2 è ancora iscritto
        assert queue2 in broadcaster._subscribers[session_id]
        assert queue1 not in broadcaster._subscribers[session_id]

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_session_if_empty(self):
        """Test: unsubscribe() rimuove la sessione se nessun subscriber"""
        # Setup
        broadcaster = SSEBroadcaster()
        session_id = 456
        queue = await broadcaster.subscribe(session_id)
        
        # Execute
        await broadcaster.unsubscribe(session_id, queue)
        
        # Verify - la session key non dovrebbe più esistere
        assert session_id not in broadcaster._subscribers

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_queue(self):
        """Test: unsubscribe() con queue inesistente non fallisce"""
        # Setup
        broadcaster = SSEBroadcaster()
        session_id = 456
        fake_queue = asyncio.Queue()
        
        # Execute - non dovrebbe lanciare eccezione
        try:
            await broadcaster.unsubscribe(session_id, fake_queue)
        except Exception as e:
            pytest.fail(f"unsubscribe sollevò eccezione: {e}")

    # ========== Test Emit ==========

    @pytest.mark.asyncio
    async def test_emit_sends_to_all_subscribers(self):
        """Test: emit() invia evento a tutti i subscriber della sessione"""
        # Setup
        broadcaster = SSEBroadcaster()
        session_id = 456
        queue1 = await broadcaster.subscribe(session_id)
        queue2 = await broadcaster.subscribe(session_id)
        
        # Execute
        event_type = "cart_update"
        data = {"items": 5}
        await broadcaster.emit(session_id, event_type, data)
        
        # Verify - entrambe le queue ricevono il messaggio
        msg1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
        msg2 = await asyncio.wait_for(queue2.get(), timeout=1.0)
        
        assert msg1 == msg2  # Stesso messaggio
        assert "cart_update" in msg1
        assert "items" in msg1

    @pytest.mark.asyncio
    async def test_emit_does_not_affect_other_sessions(self):
        """Test: emit() non invia a subscriber di altre session"""
        # Setup
        broadcaster = SSEBroadcaster()
        session_id_1 = 456
        session_id_2 = 789
        
        queue1 = await broadcaster.subscribe(session_id_1)
        queue2 = await broadcaster.subscribe(session_id_2)
        
        # Execute - emetti solo per session 1
        await broadcaster.emit(session_id_1, "test_event", {"data": "test"})
        
        # Verify
        msg1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
        assert "test_event" in msg1
        
        # queue2 non dovrebbe ricevere nulla (timeout)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue2.get(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_emit_no_subscribers(self):
        """Test: emit() con nessun subscriber non fallisce"""
        # Setup
        broadcaster = SSEBroadcaster()
        session_id = 999  # Session senza subscriber
        
        # Execute - non dovrebbe lanciare eccezione
        try:
            await broadcaster.emit(session_id, "test", {})
        except Exception as e:
            pytest.fail(f"emit sollevò eccezione: {e}")

    # ========== Test Format Event ==========

    def test_format_event_creates_valid_sse(self):
        """Test: _format_event() crea stringa SSE valida"""
        # Setup
        event_type = "cart_update"
        data = {"items": 5, "total": 100}
        
        # Execute
        result = SSEBroadcaster._format_event(event_type, data)
        
        # Verify - deve essere formato SSE
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        # Il JSON deve contenere event e data
        json_part = result[6:-2]  # Estrai la parte JSON
        parsed = json.loads(json_part)
        assert parsed["event"] == event_type
        assert parsed["data"] == data

    def test_format_event_with_nested_data(self):
        """Test: _format_event() con dati annidati"""
        # Setup
        event_type = "complex_event"
        data = {
            "user": {"id": 123, "name": "Test"},
            "items": [1, 2, 3],
        }
        
        # Execute
        result = SSEBroadcaster._format_event(event_type, data)
        
        # Verify
        json_part = result[6:-2]
        parsed = json.loads(json_part)
        assert parsed["data"]["user"]["id"] == 123
        assert parsed["data"]["items"] == [1, 2, 3]

    # ========== Test Active Connections ==========

    @pytest.mark.asyncio
    async def test_active_connections_counts_subscribers(self):
        """Test: active_connections property conta totale subscriber"""
        # Setup
        broadcaster = SSEBroadcaster()
        
        # Execute
        await broadcaster.subscribe(456)
        await broadcaster.subscribe(456)
        await broadcaster.subscribe(789)
        
        # Verify - 3 subscriber totali
        assert broadcaster.active_connections == 3

    @pytest.mark.asyncio
    async def test_active_connections_after_unsubscribe(self):
        """Test: active_connections aggiornato dopo unsubscribe"""
        # Setup
        broadcaster = SSEBroadcaster()
        queue1 = await broadcaster.subscribe(456)
        queue2 = await broadcaster.subscribe(456)
        
        # Verify
        assert broadcaster.active_connections == 2
        
        # Execute
        await broadcaster.unsubscribe(456, queue1)
        
        # Verify
        assert broadcaster.active_connections == 1

    @pytest.mark.asyncio
    async def test_active_connections_zero_initially(self):
        """Test: active_connections è 0 all'inizio"""
        # Setup
        broadcaster = SSEBroadcaster()
        
        # Verify
        assert broadcaster.active_connections == 0

    # ========== Test Singleton Pattern ==========

    def test_get_broadcaster_returns_singleton(self):
        """Test: get_broadcaster() ritorna sempre la stessa istanza"""
        # Execute
        broadcaster1 = get_broadcaster()
        broadcaster2 = get_broadcaster()
        
        # Verify
        assert broadcaster1 is broadcaster2

    def test_broadcaster_is_thread_safe(self):
        """Test: broadcaster è asyncio-safe (usa lock)"""
        # Setup
        broadcaster = SSEBroadcaster()
        
        # Verify - ha lock
        assert hasattr(broadcaster, '_lock')
        assert isinstance(broadcaster._lock, asyncio.Lock)