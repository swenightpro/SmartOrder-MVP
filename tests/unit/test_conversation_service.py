<<<<<<< Updated upstream
import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
from services.conversation_service import ConversationService


class TestConversationService:
    """Unit test per ConversationService (chat)"""

    @pytest.fixture
    def mock_db(self):
        """Mock del database adapter"""
        return Mock()

    @pytest.fixture
    def mock_ai_client(self):
        """Mock del AI client"""
        return Mock()

    @pytest.fixture
    def mock_broadcaster(self):
        """Mock del broadcaster SSE"""
        mock = Mock()
        mock.emit = AsyncMock()
        return mock

    @pytest.fixture
    def conversation_service(self, mock_db, mock_ai_client, mock_broadcaster):
        """Istanza di ConversationService con mock"""
        return ConversationService(mock_db, mock_ai_client, mock_broadcaster)

    # ========== Test Get Active Session ==========

    def test_get_active_session_exists(self, conversation_service, mock_db):
        """Test: get_active_session ritorna sessione attiva"""
        # Setup
        user_id = 123
        expected_session = {
            "id": 456,
            "user_id": user_id,
            "created_at": "2026-04-08 10:00:00",
        }
        mock_db.get_active_session.return_value = expected_session
        
        # Execute
        result = conversation_service.get_active_session(user_id)
        
        # Verify
        assert result == expected_session
        mock_db.get_active_session.assert_called_once_with(user_id)

    def test_get_active_session_not_found(self, conversation_service, mock_db):
        """Test: get_active_session ritorna None se nessuna sessione attiva"""
        # Setup
        user_id = 123
        mock_db.get_active_session.return_value = None
        
        # Execute
        result = conversation_service.get_active_session(user_id)
        
        # Verify
        assert result is None

    # ========== Test Create Session ==========

    def test_create_session(self, conversation_service, mock_db):
        """Test: create_session crea una nuova sessione"""
        # Setup
        user_id = 123
        expected_session = {
            "id": 456,
            "user_id": user_id,
            "created_at": "2026-04-08 10:00:00",
        }
        mock_db.create_session.return_value = expected_session
        
        # Execute
        result = conversation_service.create_session(user_id)
        
        # Verify
        assert result == expected_session
        mock_db.create_session.assert_called_once_with(user_id)

    # ========== Test Get Messages ==========

    def test_get_messages(self, conversation_service, mock_db):
        """Test: get_messages ritorna messaggi della sessione"""
        # Setup
        session_id = 456
        expected_messages = [
            {
                "id": 1,
                "session_id": session_id,
                "sender": "customer",
                "content": "Ciao",
                "created_at": "2026-04-08 10:05:00",
                "metadata": None,
            },
            {
                "id": 2,
                "session_id": session_id,
                "sender": "ai",
                "content": "Buongiorno!",
                "created_at": "2026-04-08 10:06:00",
                "metadata": json.dumps({"intents": ["GREETING"]}),
            },
        ]
        mock_db.get_messages.return_value = expected_messages
        
        # Execute
        result = conversation_service.get_messages(session_id)
        
        # Verify
        assert len(result) == 2
        # Verifica che metadata sia stato parsato
        assert isinstance(result[1]["metadata"], dict)
        mock_db.get_messages.assert_called_once_with(session_id)

    def test_get_messages_empty(self, conversation_service, mock_db):
        """Test: get_messages ritorna lista vuota se nessun messaggio"""
        # Setup
        session_id = 456
        mock_db.get_messages.return_value = []
        
        # Execute
        result = conversation_service.get_messages(session_id)
        
        # Verify
        assert result == []

    def test_get_messages_parses_metadata(self, conversation_service, mock_db):
        """Test: get_messages parsa correttamente metadata JSON"""
        # Setup
        session_id = 456
        metadata_str = '{"intents": ["ORDER"], "action": "ORDER_ADDED"}'
        messages = [
            {
                "id": 1,
                "session_id": session_id,
                "sender": "ai",
                "content": "Aggiunti 5 pasta",
                "created_at": "2026-04-08 10:00:00",
                "metadata": metadata_str,
            }
        ]
        mock_db.get_messages.return_value = messages
        
        # Execute
        result = conversation_service.get_messages(session_id)
        
        # Verify
        assert isinstance(result[0]["metadata"], dict)
        assert result[0]["metadata"]["intents"] == ["ORDER"]
        assert result[0]["metadata"]["action"] == "ORDER_ADDED"

    def test_get_messages_handles_invalid_metadata(self, conversation_service, mock_db):
        """Test: get_messages gestisce metadata non valido"""
        # Setup
        session_id = 456
        messages = [
            {
                "id": 1,
                "sender": "ai",
                "content": "Test",
                "metadata": "invalid json {[",
            }
        ]
        mock_db.get_messages.return_value = messages
        
        # Execute
        result = conversation_service.get_messages(session_id)
        
        # Verify - metadata rimane come stringa se non parsabile
        assert isinstance(result[0]["metadata"], str)

    def test_get_messages_handles_datetime(self, conversation_service, mock_db):
        """Test: get_messages converte created_at a stringa"""
        # Setup
        session_id = 456
        from datetime import datetime
        dt = datetime(2026, 4, 8, 10, 0, 0)
        messages = [
            {
                "id": 1,
                "sender": "customer",
                "content": "Test",
                "created_at": dt,
            }
        ]
        mock_db.get_messages.return_value = messages
        
        # Execute
        result = conversation_service.get_messages(session_id)
        
        # Verify
        assert isinstance(result[0]["created_at"], str)

    # ========== Test Save Message (delegato a db) ==========

    def test_get_messages_calls_db_with_session_id(self, conversation_service, mock_db):
        """Test: get_messages chiama db.get_messages con session_id corretto"""
        # Setup
        session_id = 789
        mock_db.get_messages.return_value = []

        # Execute
        conversation_service.get_messages(session_id)

        # Verify
        mock_db.get_messages.assert_called_once_with(session_id)

    # ========== Test Transcribe Audio (TU116) ==========

    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, conversation_service, mock_ai_client):
        """Test: transcribe_audio delega al client AI"""
        # Setup
        mock_audio_file = Mock()
        filename = "audio.wav"
        mock_ai_client.transcribe_audio = AsyncMock(return_value="Vorrei della pasta")

        # Execute
        result = await conversation_service.transcribe_audio(mock_audio_file, filename)

        # Verify
        assert result == "Vorrei della pasta"
        mock_ai_client.transcribe_audio.assert_called_once_with(mock_audio_file, filename)

    @pytest.mark.asyncio
    async def test_transcribe_audio_empty_result(self, conversation_service, mock_ai_client):
        """Test: transcribe_audio con risultato vuoto"""
        mock_ai_client.transcribe_audio = AsyncMock(return_value="")

        result = await conversation_service.transcribe_audio(Mock(), "test.wav")

        assert result == ""

    # ========== Test Save Message to Session (TU117) ==========

    def test_save_message_to_session_success(self, conversation_service, mock_db):
        """Test: save_message_to_session salva e ritorna ID messaggio"""
        # Setup
        session_id = 456
        sender = "user"
        content = "Vorrei ordinare pasta"
        mock_db.save_message.return_value = 789

        # Execute
        result = conversation_service.save_message_to_session(session_id, sender, content)

        # Verify
        assert result == 789
        mock_db.save_message.assert_called_once_with(session_id, sender, content)

    def test_save_message_to_session_operator(self, conversation_service, mock_db):
        """Test: save_message_to_session con sender operator"""
        mock_db.save_message.return_value = 790

        result = conversation_service.save_message_to_session(456, "operator", "Ti aiuto io")

        assert result == 790
        mock_db.save_message.assert_called_once_with(456, "operator", "Ti aiuto io")

    # ========== Test Handle Message (TU118) ==========

    @pytest.mark.asyncio
    async def test_handle_message_greeting(self, conversation_service, mock_db, mock_broadcaster):
        """Test: handle_message con saluto ritorna risposta di saluto"""
        # Setup — handle_message chiama _load_history_from_db → get_messages
        mock_db.get_messages.return_value = []
        mock_db.get_cart_by_client.return_value = []
        mock_db.get_last_orders.return_value = []
        mock_db.save_message.return_value = 1

        # Execute
        result = await conversation_service.handle_message(
            message="Ciao",
            client_id=100,
            session_id=456,
        )

        # Verify
        assert result is not None
        assert "message" in result or "response" in result
        # Il saluto non dovrebbe aggiungere prodotti
        assert result.get("order_confirmed") is False

    @pytest.mark.asyncio
    async def test_handle_message_returns_dict(self, conversation_service, mock_db, mock_ai_client, mock_broadcaster):
        """Test: handle_message ritorna sempre un dizionario con le chiavi attese"""
        # Setup — "il solito" shortcut chiama _handle_usual_request
        mock_db.get_messages.return_value = []
        mock_db.get_cart_by_client.return_value = []
        mock_db.get_last_orders.return_value = []
        mock_db.get_order_history_flat.return_value = []
        mock_db.get_available_cod_art.return_value = []
        mock_db.save_message.return_value = 1

        # Execute con frase "il solito"
        result = await conversation_service.handle_message(
            message="il solito",
            client_id=100,
            session_id=456,
        )

        # Verify - deve avere almeno "message"
        assert isinstance(result, dict)
        assert "message" in result
=======
import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
from services.conversation_service import ConversationService


class TestConversationService:
    """Unit test per ConversationService (chat)"""

    @pytest.fixture
    def mock_db(self):
        """Mock del database adapter"""
        return Mock()

    @pytest.fixture
    def mock_ai_client(self):
        """Mock del AI client"""
        return Mock()

    @pytest.fixture
    def mock_broadcaster(self):
        """Mock del broadcaster SSE"""
        mock = Mock()
        mock.emit = AsyncMock()
        return mock

    @pytest.fixture
    def conversation_service(self, mock_db, mock_ai_client, mock_broadcaster):
        """Istanza di ConversationService con mock"""
        return ConversationService(mock_db, mock_ai_client, mock_broadcaster)

    # ========== Test Get Active Session ==========

    def test_get_active_session_exists(self, conversation_service, mock_db):
        """Test: get_active_session ritorna sessione attiva"""
        # Setup
        user_id = 123
        expected_session = {
            "id": 456,
            "user_id": user_id,
            "created_at": "2026-04-08 10:00:00",
        }
        mock_db.get_active_session.return_value = expected_session
        
        # Execute
        result = conversation_service.get_active_session(user_id)
        
        # Verify
        assert result == expected_session
        mock_db.get_active_session.assert_called_once_with(user_id)

    def test_get_active_session_not_found(self, conversation_service, mock_db):
        """Test: get_active_session ritorna None se nessuna sessione attiva"""
        # Setup
        user_id = 123
        mock_db.get_active_session.return_value = None
        
        # Execute
        result = conversation_service.get_active_session(user_id)
        
        # Verify
        assert result is None

    # ========== Test Create Session ==========

    def test_create_session(self, conversation_service, mock_db):
        """Test: create_session crea una nuova sessione"""
        # Setup
        user_id = 123
        expected_session = {
            "id": 456,
            "user_id": user_id,
            "created_at": "2026-04-08 10:00:00",
        }
        mock_db.create_session.return_value = expected_session
        
        # Execute
        result = conversation_service.create_session(user_id)
        
        # Verify
        assert result == expected_session
        mock_db.create_session.assert_called_once_with(user_id)

    # ========== Test Get Messages ==========

    def test_get_messages(self, conversation_service, mock_db):
        """Test: get_messages ritorna messaggi della sessione"""
        # Setup
        session_id = 456
        expected_messages = [
            {
                "id": 1,
                "session_id": session_id,
                "sender": "customer",
                "content": "Ciao",
                "created_at": "2026-04-08 10:05:00",
                "metadata": None,
            },
            {
                "id": 2,
                "session_id": session_id,
                "sender": "ai",
                "content": "Buongiorno!",
                "created_at": "2026-04-08 10:06:00",
                "metadata": json.dumps({"intents": ["GREETING"]}),
            },
        ]
        mock_db.get_messages.return_value = expected_messages
        
        # Execute
        result = conversation_service.get_messages(session_id)
        
        # Verify
        assert len(result) == 2
        # Verifica che metadata sia stato parsato
        assert isinstance(result[1]["metadata"], dict)
        mock_db.get_messages.assert_called_once_with(session_id)

    def test_get_messages_empty(self, conversation_service, mock_db):
        """Test: get_messages ritorna lista vuota se nessun messaggio"""
        # Setup
        session_id = 456
        mock_db.get_messages.return_value = []
        
        # Execute
        result = conversation_service.get_messages(session_id)
        
        # Verify
        assert result == []

    def test_get_messages_parses_metadata(self, conversation_service, mock_db):
        """Test: get_messages parsa correttamente metadata JSON"""
        # Setup
        session_id = 456
        metadata_str = '{"intents": ["ORDER"], "action": "ORDER_ADDED"}'
        messages = [
            {
                "id": 1,
                "session_id": session_id,
                "sender": "ai",
                "content": "Aggiunti 5 pasta",
                "created_at": "2026-04-08 10:00:00",
                "metadata": metadata_str,
            }
        ]
        mock_db.get_messages.return_value = messages
        
        # Execute
        result = conversation_service.get_messages(session_id)
        
        # Verify
        assert isinstance(result[0]["metadata"], dict)
        assert result[0]["metadata"]["intents"] == ["ORDER"]
        assert result[0]["metadata"]["action"] == "ORDER_ADDED"

    def test_get_messages_handles_invalid_metadata(self, conversation_service, mock_db):
        """Test: get_messages gestisce metadata non valido"""
        # Setup
        session_id = 456
        messages = [
            {
                "id": 1,
                "sender": "ai",
                "content": "Test",
                "metadata": "invalid json {[",
            }
        ]
        mock_db.get_messages.return_value = messages
        
        # Execute
        result = conversation_service.get_messages(session_id)
        
        # Verify - metadata rimane come stringa se non parsabile
        assert isinstance(result[0]["metadata"], str)

    def test_get_messages_handles_datetime(self, conversation_service, mock_db):
        """Test: get_messages converte created_at a stringa"""
        # Setup
        session_id = 456
        from datetime import datetime
        dt = datetime(2026, 4, 8, 10, 0, 0)
        messages = [
            {
                "id": 1,
                "sender": "customer",
                "content": "Test",
                "created_at": dt,
            }
        ]
        mock_db.get_messages.return_value = messages
        
        # Execute
        result = conversation_service.get_messages(session_id)
        
        # Verify
        assert isinstance(result[0]["created_at"], str)

    # ========== Test Save Message (delegato a db) ==========

    def test_get_messages_calls_db_with_session_id(self, conversation_service, mock_db):
        """Test: get_messages chiama db.get_messages con session_id corretto"""
        # Setup
        session_id = 789
        mock_db.get_messages.return_value = []

        # Execute
        conversation_service.get_messages(session_id)

        # Verify
        mock_db.get_messages.assert_called_once_with(session_id)

    # ========== Test Transcribe Audio (TU116) ==========

    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, conversation_service, mock_ai_client):
        """Test: transcribe_audio delega al client AI"""
        # Setup
        mock_audio_file = Mock()
        filename = "audio.wav"
        mock_ai_client.transcribe_audio = AsyncMock(return_value="Vorrei della pasta")

        # Execute
        result = await conversation_service.transcribe_audio(mock_audio_file, filename)

        # Verify
        assert result == "Vorrei della pasta"
        mock_ai_client.transcribe_audio.assert_called_once_with(mock_audio_file, filename)

    @pytest.mark.asyncio
    async def test_transcribe_audio_empty_result(self, conversation_service, mock_ai_client):
        """Test: transcribe_audio con risultato vuoto"""
        mock_ai_client.transcribe_audio = AsyncMock(return_value="")

        result = await conversation_service.transcribe_audio(Mock(), "test.wav")

        assert result == ""

    # ========== Test Save Message to Session (TU117) ==========

    def test_save_message_to_session_success(self, conversation_service, mock_db):
        """Test: save_message_to_session salva e ritorna ID messaggio"""
        # Setup
        session_id = 456
        sender = "user"
        content = "Vorrei ordinare pasta"
        mock_db.save_message.return_value = 789

        # Execute
        result = conversation_service.save_message_to_session(session_id, sender, content)

        # Verify
        assert result == 789
        mock_db.save_message.assert_called_once_with(session_id, sender, content)

    def test_save_message_to_session_operator(self, conversation_service, mock_db):
        """Test: save_message_to_session con sender operator"""
        mock_db.save_message.return_value = 790

        result = conversation_service.save_message_to_session(456, "operator", "Ti aiuto io")

        assert result == 790
        mock_db.save_message.assert_called_once_with(456, "operator", "Ti aiuto io")

    # ========== Test Handle Message (TU118) ==========

    @pytest.mark.asyncio
    async def test_handle_message_greeting(self, conversation_service, mock_db, mock_broadcaster):
        """Test: handle_message con saluto ritorna risposta di saluto"""
        # Setup — handle_message chiama _load_history_from_db → get_messages
        mock_db.get_messages.return_value = []
        mock_db.get_cart_by_client.return_value = []
        mock_db.get_last_orders.return_value = []
        mock_db.save_message.return_value = 1

        # Execute
        result = await conversation_service.handle_message(
            message="Ciao",
            client_id=100,
            session_id=456,
        )

        # Verify
        assert result is not None
        assert "message" in result or "response" in result
        # Il saluto non dovrebbe aggiungere prodotti
        assert result.get("order_confirmed") is False

    @pytest.mark.asyncio
    async def test_handle_message_returns_dict(self, conversation_service, mock_db, mock_ai_client, mock_broadcaster):
        """Test: handle_message ritorna sempre un dizionario con le chiavi attese"""
        # Setup — "il solito" shortcut chiama _handle_usual_request
        mock_db.get_messages.return_value = []
        mock_db.get_cart_by_client.return_value = []
        mock_db.get_last_orders.return_value = []
        mock_db.get_order_history_flat.return_value = []
        mock_db.get_available_cod_art.return_value = []
        mock_db.save_message.return_value = 1

        # Execute con frase "il solito"
        result = await conversation_service.handle_message(
            message="il solito",
            client_id=100,
            session_id=456,
        )

        # Verify - deve avere almeno "message"
        assert isinstance(result, dict)
        assert "message" in result
>>>>>>> Stashed changes
