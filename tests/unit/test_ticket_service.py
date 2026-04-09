<<<<<<< Updated upstream
import pytest
from unittest.mock import Mock, AsyncMock
from services.ticket_service import TicketService


class TestTicketService:
    """Unit test per TicketService (ticketing)"""

    @pytest.fixture
    def mock_ticket_repo(self):
        """Mock del ticket repository"""
        return Mock()

    @pytest.fixture
    def mock_db_adapter(self):
        """Mock del database adapter"""
        return Mock()

    @pytest.fixture
    def mock_broadcaster(self):
        """Mock del broadcaster SSE"""
        mock = Mock()
        mock.emit = AsyncMock()
        return mock

    @pytest.fixture
    def ticket_service(self, mock_ticket_repo, mock_db_adapter, mock_broadcaster):
        """Istanza di TicketService con mock"""
        return TicketService(mock_ticket_repo, mock_db_adapter, mock_broadcaster)

    # ========== Test Create Ticket ==========

    def test_create_ticket_success(self, ticket_service, mock_ticket_repo, mock_db_adapter):
        """Test: create_ticket crea ticket e aggiunge messaggio di sistema"""
        # Setup
        session_id = 456
        cod_cli = 100
        expected_ticket = {
            "id": 1,
            "session_id": session_id,
            "cod_cli": cod_cli,
            "status": "aperto",
        }
        mock_ticket_repo.create_ticket.return_value = expected_ticket
        mock_db_adapter.save_message.return_value = 789
        
        # Execute
        result = ticket_service.create_ticket(session_id, cod_cli)
        
        # Verify
        assert result == expected_ticket
        mock_ticket_repo.create_ticket.assert_called_once_with(session_id, cod_cli)
        # Verifica che il messaggio di sistema sia stato salvato
        mock_db_adapter.save_message.assert_called_once()

    def test_create_ticket_no_db_adapter(self, mock_ticket_repo):
        """Test: create_ticket senza db_adapter non fallisce"""
        # Setup
        service = TicketService(mock_ticket_repo, db_adapter=None, broadcaster=None)
        session_id = 456
        cod_cli = 100
        expected_ticket = {
            "id": 1,
            "session_id": session_id,
            "cod_cli": cod_cli,
        }
        mock_ticket_repo.create_ticket.return_value = expected_ticket
        
        # Execute
        result = service.create_ticket(session_id, cod_cli)
        
        # Verify
        assert result == expected_ticket

    # ========== Test Get Open Tickets ==========

    def test_get_open_tickets(self, ticket_service, mock_ticket_repo, mock_db_adapter):
        """Test: get_open_tickets ritorna ticket aperti arricchiti"""
        # Setup
        tickets = [
            {
                "id": 1,
                "session_id": 456,
                "cod_cli": 100,
                "created_at": "2026-04-08 10:00:00",
            }
        ]
        mock_ticket_repo.get_open_tickets.return_value = tickets
        mock_db_adapter.get_client_info.return_value = {"rag_soc": "Company A"}
        
        # Execute
        result = ticket_service.get_open_tickets()
        
        # Verify
        assert len(result) == 1
        assert result[0]["rag_soc"] == "Company A"

    def test_get_open_tickets_empty(self, ticket_service, mock_ticket_repo):
        """Test: get_open_tickets ritorna lista vuota se nessun ticket aperto"""
        # Setup
        mock_ticket_repo.get_open_tickets.return_value = []
        
        # Execute
        result = ticket_service.get_open_tickets()
        
        # Verify
        assert result == []

    # ========== Test Get Ticket by ID ==========

    def test_get_ticket_by_id_success(self, ticket_service, mock_ticket_repo, mock_db_adapter):
        """Test: get_ticket_by_id ritorna ticket arricchito con dati"""
        # Setup
        ticket_id = 1
        expected_ticket = {
            "id": ticket_id,
            "session_id": 456,
            "cod_cli": 100,
        }
        mock_ticket_repo.get_ticket_by_id.return_value = expected_ticket
        mock_db_adapter.get_client_info.return_value = {"rag_soc": "Company A"}
        mock_db_adapter.get_messages_with_feedback.return_value = [
            {"id": 1, "content": "Aiuto!"}
        ]
        mock_db_adapter.get_cart_by_session.return_value = []
        
        # Execute
        result = ticket_service.get_ticket_by_id(ticket_id)
        
        # Verify
        assert result is not None
        assert result["rag_soc"] == "Company A"
        assert "messages" in result
        assert "cart_items" in result

    def test_get_ticket_by_id_not_found(self, ticket_service, mock_ticket_repo):
        """Test: get_ticket_by_id ritorna None se ticket non trovato"""
        # Setup
        ticket_id = 999
        mock_ticket_repo.get_ticket_by_id.return_value = None
        
        # Execute
        result = ticket_service.get_ticket_by_id(ticket_id)
        
        # Verify
        assert result is None

    # ========== Test Lock/Unlock Ticket ==========

    @pytest.mark.asyncio
    async def test_lock_ticket_success(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: lock_ticket locka il ticket per un operatore"""
        # Setup
        ticket_id = 1
        operator_id = 123
        mock_ticket_repo.lock_ticket.return_value = True
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": ticket_id,
            "session_id": 456,
        }
        
        # Execute
        result = await ticket_service.lock_ticket(ticket_id, operator_id)
        
        # Verify
        assert result is True
        mock_ticket_repo.lock_ticket.assert_called_once_with(ticket_id, operator_id)

    @pytest.mark.asyncio
    async def test_lock_ticket_already_locked(self, ticket_service, mock_ticket_repo):
        """Test: lock_ticket ritorna False se già lockato"""
        # Setup
        ticket_id = 1
        operator_id = 123
        mock_ticket_repo.lock_ticket.return_value = False
        
        # Execute
        result = await ticket_service.lock_ticket(ticket_id, operator_id)
        
        # Verify
        assert result is False

    def test_get_platform_usage_overview(self, ticket_service, mock_ticket_repo):
        """Test: get_platform_usage_overview ritorna metriche"""
        # Setup
        expected_overview = {
            "total_tickets": 100,
            "open_tickets": 5,
            "avg_wait_time": 120,
        }
        mock_ticket_repo.get_platform_usage_overview.return_value = expected_overview
        
        # Execute
        result = ticket_service.get_platform_usage_overview(days=7)
        
        # Verify
        assert result == expected_overview
        mock_ticket_repo.get_platform_usage_overview.assert_called_once()

    def test_get_platform_usage_overview_clamps_days(self, ticket_service, mock_ticket_repo):
        """Test: get_platform_usage_overview limita i giorni a 7-90"""
        # Setup
        mock_ticket_repo.get_platform_usage_overview.return_value = {}
        
        # Execute con giorni troppo bassi
        ticket_service.get_platform_usage_overview(days=2)
        # Dovrebbe clampare a min(7, max(90, 2)) = 7
        
        # Verify
        called_days = mock_ticket_repo.get_platform_usage_overview.call_args[0][0]
        assert called_days == 7

    def test_get_platform_usage_overview_clamps_high(self, ticket_service, mock_ticket_repo):
        """Test: get_platform_usage_overview limita giorni a max 90"""
        # Setup
        mock_ticket_repo.get_platform_usage_overview.return_value = {}

        # Execute con giorni troppo alti
        ticket_service.get_platform_usage_overview(days=200)

        # Verify
        called_days = mock_ticket_repo.get_platform_usage_overview.call_args[0][0]
        assert called_days == 90

    # ========== Test Unlock Ticket (TU123) ==========

    @pytest.mark.asyncio
    async def test_unlock_ticket_success(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: unlock_ticket rilascia il lock e notifica via SSE"""
        # Setup
        ticket_id = 1
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": ticket_id,
            "session_id": 456,
        }

        # Execute
        await ticket_service.unlock_ticket(ticket_id)

        # Verify
        mock_ticket_repo.unlock_ticket.assert_called_once_with(ticket_id)
        # Verifica emissione SSE (session + operator channel)
        assert mock_broadcaster.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_unlock_ticket_no_session(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: unlock_ticket senza session_id non emette SSE"""
        # Setup
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": 1,
            "session_id": None,
        }

        # Execute
        await ticket_service.unlock_ticket(1)

        # Verify
        mock_ticket_repo.unlock_ticket.assert_called_once_with(1)
        mock_broadcaster.emit.assert_not_called()

    # ========== Test Close Ticket (TU124) ==========

    @pytest.mark.asyncio
    async def test_close_ticket_success(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: close_ticket chiude il ticket e notifica via SSE"""
        # Setup
        ticket_id = 1
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": ticket_id,
            "session_id": 456,
        }

        # Execute
        await ticket_service.close_ticket(ticket_id)

        # Verify
        mock_ticket_repo.close_ticket.assert_called_once_with(ticket_id)
        assert mock_broadcaster.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_close_ticket_no_ticket(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: close_ticket con ticket inesistente non emette SSE"""
        # Setup
        mock_ticket_repo.get_ticket_by_id.return_value = None

        # Execute
        await ticket_service.close_ticket(999)

        # Verify
        mock_ticket_repo.close_ticket.assert_called_once_with(999)
        mock_broadcaster.emit.assert_not_called()

    # ========== Test Send Chat Message (TU125) ==========

    @pytest.mark.asyncio
    async def test_send_chat_message_success(self, ticket_service, mock_ticket_repo, mock_db_adapter, mock_broadcaster):
        """Test: send_chat_message invia messaggio operatore"""
        # Setup
        ticket_id = 1
        content = "Ciao, ti aiuto io"
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": ticket_id,
            "session_id": 456,
            "status": "in_lavorazione",
        }
        mock_db_adapter.send_message.return_value = 789

        # Execute
        result = await ticket_service.send_chat_message(ticket_id, content)

        # Verify
        assert result["id"] == 789
        assert result["sender"] == "operator"
        assert result["content"] == content
        mock_db_adapter.send_message.assert_called_once_with(456, "operator", content)
        mock_broadcaster.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_chat_message_ticket_not_found(self, ticket_service, mock_ticket_repo):
        """Test: send_chat_message solleva errore se ticket non trovato"""
        mock_ticket_repo.get_ticket_by_id.return_value = None

        with pytest.raises(ValueError, match="non trovato"):
            await ticket_service.send_chat_message(999, "test")

    @pytest.mark.asyncio
    async def test_send_chat_message_ticket_closed(self, ticket_service, mock_ticket_repo):
        """Test: send_chat_message solleva errore se ticket chiuso"""
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": 1,
            "session_id": 456,
            "status": "chiuso",
        }

        with pytest.raises(ValueError, match="chiuso"):
            await ticket_service.send_chat_message(1, "test")

    @pytest.mark.asyncio
    async def test_send_chat_message_no_session(self, ticket_service, mock_ticket_repo):
        """Test: send_chat_message solleva errore se ticket senza sessione"""
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": 1,
            "session_id": None,
            "status": "in_lavorazione",
        }

        with pytest.raises(ValueError, match="senza sessione"):
            await ticket_service.send_chat_message(1, "test")

    # ========== Test Get Ticket by Session (TU126) ==========

    def test_get_ticket_by_session_found(self, ticket_service, mock_ticket_repo, mock_db_adapter):
        """Test: get_ticket_by_session ritorna ticket arricchito"""
        # Setup
        session_id = 456
        mock_ticket_repo.get_ticket_by_session.return_value = {
            "id": 1,
            "session_id": session_id,
            "cod_cli": 100,
        }
        mock_db_adapter.get_client_info.return_value = {"rag_soc": "Company A"}

        # Execute
        result = ticket_service.get_ticket_by_session(session_id)

        # Verify
        assert result is not None
        assert result["rag_soc"] == "Company A"

    def test_get_ticket_by_session_not_found(self, ticket_service, mock_ticket_repo):
        """Test: get_ticket_by_session ritorna None se non trovato"""
        mock_ticket_repo.get_ticket_by_session.return_value = None

        result = ticket_service.get_ticket_by_session(456)

        assert result is None

    # ========== Test Close Ticket by Session (TU127) ==========

    @pytest.mark.asyncio
    async def test_close_ticket_by_session_success(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: close_ticket_by_session chiude il ticket della sessione"""
        # Setup
        session_id = 456
        mock_ticket_repo.get_ticket_by_session.return_value = {
            "id": 1,
            "session_id": session_id,
        }
        # close_ticket needs get_ticket_by_id
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": 1,
            "session_id": session_id,
        }

        # Execute
        await ticket_service.close_ticket_by_session(session_id)

        # Verify
        mock_ticket_repo.close_ticket.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_close_ticket_by_session_not_found(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: close_ticket_by_session non fa nulla se nessun ticket"""
        mock_ticket_repo.get_ticket_by_session.return_value = None

        # Execute — non dovrebbe sollevare eccezioni
        await ticket_service.close_ticket_by_session(456)

        # Verify
        mock_ticket_repo.close_ticket.assert_not_called()

    # ========== Test Save Customer Message (TU128) ==========

    @pytest.mark.asyncio
    async def test_save_customer_message_success(self, ticket_service, mock_db_adapter, mock_broadcaster):
        """Test: save_customer_message salva messaggio e notifica via SSE"""
        # Setup
        session_id = 456
        content = "Ho bisogno di aiuto"
        mock_db_adapter.send_message.return_value = 789

        # Execute
        result = await ticket_service.save_customer_message(session_id, content)

        # Verify
        assert result["id"] == 789
        assert result["sender"] == "user"
        assert result["content"] == content
        mock_db_adapter.send_message.assert_called_once_with(session_id, "user", content)
        # Emette su OPERATOR_CHANNEL e session_id
        assert mock_broadcaster.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_save_customer_message_no_broadcaster(self, mock_ticket_repo, mock_db_adapter):
        """Test: save_customer_message senza broadcaster non fallisce"""
        service = TicketService(mock_ticket_repo, mock_db_adapter, broadcaster=None)
        mock_db_adapter.send_message.return_value = 789

        result = await service.save_customer_message(456, "test")

        assert result["id"] == 789
        assert result["sender"] == "user"
=======
import pytest
from unittest.mock import Mock, AsyncMock
from services.ticket_service import TicketService


class TestTicketService:
    """Unit test per TicketService (ticketing)"""

    @pytest.fixture
    def mock_ticket_repo(self):
        """Mock del ticket repository"""
        return Mock()

    @pytest.fixture
    def mock_db_adapter(self):
        """Mock del database adapter"""
        return Mock()

    @pytest.fixture
    def mock_broadcaster(self):
        """Mock del broadcaster SSE"""
        mock = Mock()
        mock.emit = AsyncMock()
        return mock

    @pytest.fixture
    def ticket_service(self, mock_ticket_repo, mock_db_adapter, mock_broadcaster):
        """Istanza di TicketService con mock"""
        return TicketService(mock_ticket_repo, mock_db_adapter, mock_broadcaster)

    # ========== Test Create Ticket ==========

    def test_create_ticket_success(self, ticket_service, mock_ticket_repo, mock_db_adapter):
        """Test: create_ticket crea ticket e aggiunge messaggio di sistema"""
        # Setup
        session_id = 456
        cod_cli = 100
        expected_ticket = {
            "id": 1,
            "session_id": session_id,
            "cod_cli": cod_cli,
            "status": "aperto",
        }
        mock_ticket_repo.create_ticket.return_value = expected_ticket
        mock_db_adapter.save_message.return_value = 789
        
        # Execute
        result = ticket_service.create_ticket(session_id, cod_cli)
        
        # Verify
        assert result == expected_ticket
        mock_ticket_repo.create_ticket.assert_called_once_with(session_id, cod_cli)
        # Verifica che il messaggio di sistema sia stato salvato
        mock_db_adapter.save_message.assert_called_once()

    def test_create_ticket_no_db_adapter(self, mock_ticket_repo):
        """Test: create_ticket senza db_adapter non fallisce"""
        # Setup
        service = TicketService(mock_ticket_repo, db_adapter=None, broadcaster=None)
        session_id = 456
        cod_cli = 100
        expected_ticket = {
            "id": 1,
            "session_id": session_id,
            "cod_cli": cod_cli,
        }
        mock_ticket_repo.create_ticket.return_value = expected_ticket
        
        # Execute
        result = service.create_ticket(session_id, cod_cli)
        
        # Verify
        assert result == expected_ticket

    # ========== Test Get Open Tickets ==========

    def test_get_open_tickets(self, ticket_service, mock_ticket_repo, mock_db_adapter):
        """Test: get_open_tickets ritorna ticket aperti arricchiti"""
        # Setup
        tickets = [
            {
                "id": 1,
                "session_id": 456,
                "cod_cli": 100,
                "created_at": "2026-04-08 10:00:00",
            }
        ]
        mock_ticket_repo.get_open_tickets.return_value = tickets
        mock_db_adapter.get_client_info.return_value = {"rag_soc": "Company A"}
        
        # Execute
        result = ticket_service.get_open_tickets()
        
        # Verify
        assert len(result) == 1
        assert result[0]["rag_soc"] == "Company A"

    def test_get_open_tickets_empty(self, ticket_service, mock_ticket_repo):
        """Test: get_open_tickets ritorna lista vuota se nessun ticket aperto"""
        # Setup
        mock_ticket_repo.get_open_tickets.return_value = []
        
        # Execute
        result = ticket_service.get_open_tickets()
        
        # Verify
        assert result == []

    # ========== Test Get Ticket by ID ==========

    def test_get_ticket_by_id_success(self, ticket_service, mock_ticket_repo, mock_db_adapter):
        """Test: get_ticket_by_id ritorna ticket arricchito con dati"""
        # Setup
        ticket_id = 1
        expected_ticket = {
            "id": ticket_id,
            "session_id": 456,
            "cod_cli": 100,
        }
        mock_ticket_repo.get_ticket_by_id.return_value = expected_ticket
        mock_db_adapter.get_client_info.return_value = {"rag_soc": "Company A"}
        mock_db_adapter.get_messages_with_feedback.return_value = [
            {"id": 1, "content": "Aiuto!"}
        ]
        mock_db_adapter.get_cart_by_session.return_value = []
        
        # Execute
        result = ticket_service.get_ticket_by_id(ticket_id)
        
        # Verify
        assert result is not None
        assert result["rag_soc"] == "Company A"
        assert "messages" in result
        assert "cart_items" in result

    def test_get_ticket_by_id_not_found(self, ticket_service, mock_ticket_repo):
        """Test: get_ticket_by_id ritorna None se ticket non trovato"""
        # Setup
        ticket_id = 999
        mock_ticket_repo.get_ticket_by_id.return_value = None
        
        # Execute
        result = ticket_service.get_ticket_by_id(ticket_id)
        
        # Verify
        assert result is None

    # ========== Test Lock/Unlock Ticket ==========

    @pytest.mark.asyncio
    async def test_lock_ticket_success(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: lock_ticket locka il ticket per un operatore"""
        # Setup
        ticket_id = 1
        operator_id = 123
        mock_ticket_repo.lock_ticket.return_value = True
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": ticket_id,
            "session_id": 456,
        }
        
        # Execute
        result = await ticket_service.lock_ticket(ticket_id, operator_id)
        
        # Verify
        assert result is True
        mock_ticket_repo.lock_ticket.assert_called_once_with(ticket_id, operator_id)

    @pytest.mark.asyncio
    async def test_lock_ticket_already_locked(self, ticket_service, mock_ticket_repo):
        """Test: lock_ticket ritorna False se già lockato"""
        # Setup
        ticket_id = 1
        operator_id = 123
        mock_ticket_repo.lock_ticket.return_value = False
        
        # Execute
        result = await ticket_service.lock_ticket(ticket_id, operator_id)
        
        # Verify
        assert result is False

    def test_get_platform_usage_overview(self, ticket_service, mock_ticket_repo):
        """Test: get_platform_usage_overview ritorna metriche"""
        # Setup
        expected_overview = {
            "total_tickets": 100,
            "open_tickets": 5,
            "avg_wait_time": 120,
        }
        mock_ticket_repo.get_platform_usage_overview.return_value = expected_overview
        
        # Execute
        result = ticket_service.get_platform_usage_overview(days=7)
        
        # Verify
        assert result == expected_overview
        mock_ticket_repo.get_platform_usage_overview.assert_called_once()

    def test_get_platform_usage_overview_clamps_days(self, ticket_service, mock_ticket_repo):
        """Test: get_platform_usage_overview limita i giorni a 7-90"""
        # Setup
        mock_ticket_repo.get_platform_usage_overview.return_value = {}
        
        # Execute con giorni troppo bassi
        ticket_service.get_platform_usage_overview(days=2)
        # Dovrebbe clampare a min(7, max(90, 2)) = 7
        
        # Verify
        called_days = mock_ticket_repo.get_platform_usage_overview.call_args[0][0]
        assert called_days == 7

    def test_get_platform_usage_overview_clamps_high(self, ticket_service, mock_ticket_repo):
        """Test: get_platform_usage_overview limita giorni a max 90"""
        # Setup
        mock_ticket_repo.get_platform_usage_overview.return_value = {}

        # Execute con giorni troppo alti
        ticket_service.get_platform_usage_overview(days=200)

        # Verify
        called_days = mock_ticket_repo.get_platform_usage_overview.call_args[0][0]
        assert called_days == 90

    # ========== Test Unlock Ticket (TU123) ==========

    @pytest.mark.asyncio
    async def test_unlock_ticket_success(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: unlock_ticket rilascia il lock e notifica via SSE"""
        # Setup
        ticket_id = 1
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": ticket_id,
            "session_id": 456,
        }

        # Execute
        await ticket_service.unlock_ticket(ticket_id)

        # Verify
        mock_ticket_repo.unlock_ticket.assert_called_once_with(ticket_id)
        # Verifica emissione SSE (session + operator channel)
        assert mock_broadcaster.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_unlock_ticket_no_session(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: unlock_ticket senza session_id non emette SSE"""
        # Setup
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": 1,
            "session_id": None,
        }

        # Execute
        await ticket_service.unlock_ticket(1)

        # Verify
        mock_ticket_repo.unlock_ticket.assert_called_once_with(1)
        mock_broadcaster.emit.assert_not_called()

    # ========== Test Close Ticket (TU124) ==========

    @pytest.mark.asyncio
    async def test_close_ticket_success(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: close_ticket chiude il ticket e notifica via SSE"""
        # Setup
        ticket_id = 1
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": ticket_id,
            "session_id": 456,
        }

        # Execute
        await ticket_service.close_ticket(ticket_id)

        # Verify
        mock_ticket_repo.close_ticket.assert_called_once_with(ticket_id)
        assert mock_broadcaster.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_close_ticket_no_ticket(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: close_ticket con ticket inesistente non emette SSE"""
        # Setup
        mock_ticket_repo.get_ticket_by_id.return_value = None

        # Execute
        await ticket_service.close_ticket(999)

        # Verify
        mock_ticket_repo.close_ticket.assert_called_once_with(999)
        mock_broadcaster.emit.assert_not_called()

    # ========== Test Send Chat Message (TU125) ==========

    @pytest.mark.asyncio
    async def test_send_chat_message_success(self, ticket_service, mock_ticket_repo, mock_db_adapter, mock_broadcaster):
        """Test: send_chat_message invia messaggio operatore"""
        # Setup
        ticket_id = 1
        content = "Ciao, ti aiuto io"
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": ticket_id,
            "session_id": 456,
            "status": "in_lavorazione",
        }
        mock_db_adapter.send_message.return_value = 789

        # Execute
        result = await ticket_service.send_chat_message(ticket_id, content)

        # Verify
        assert result["id"] == 789
        assert result["sender"] == "operator"
        assert result["content"] == content
        mock_db_adapter.send_message.assert_called_once_with(456, "operator", content)
        mock_broadcaster.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_chat_message_ticket_not_found(self, ticket_service, mock_ticket_repo):
        """Test: send_chat_message solleva errore se ticket non trovato"""
        mock_ticket_repo.get_ticket_by_id.return_value = None

        with pytest.raises(ValueError, match="non trovato"):
            await ticket_service.send_chat_message(999, "test")

    @pytest.mark.asyncio
    async def test_send_chat_message_ticket_closed(self, ticket_service, mock_ticket_repo):
        """Test: send_chat_message solleva errore se ticket chiuso"""
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": 1,
            "session_id": 456,
            "status": "chiuso",
        }

        with pytest.raises(ValueError, match="chiuso"):
            await ticket_service.send_chat_message(1, "test")

    @pytest.mark.asyncio
    async def test_send_chat_message_no_session(self, ticket_service, mock_ticket_repo):
        """Test: send_chat_message solleva errore se ticket senza sessione"""
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": 1,
            "session_id": None,
            "status": "in_lavorazione",
        }

        with pytest.raises(ValueError, match="senza sessione"):
            await ticket_service.send_chat_message(1, "test")

    # ========== Test Get Ticket by Session (TU126) ==========

    def test_get_ticket_by_session_found(self, ticket_service, mock_ticket_repo, mock_db_adapter):
        """Test: get_ticket_by_session ritorna ticket arricchito"""
        # Setup
        session_id = 456
        mock_ticket_repo.get_ticket_by_session.return_value = {
            "id": 1,
            "session_id": session_id,
            "cod_cli": 100,
        }
        mock_db_adapter.get_client_info.return_value = {"rag_soc": "Company A"}

        # Execute
        result = ticket_service.get_ticket_by_session(session_id)

        # Verify
        assert result is not None
        assert result["rag_soc"] == "Company A"

    def test_get_ticket_by_session_not_found(self, ticket_service, mock_ticket_repo):
        """Test: get_ticket_by_session ritorna None se non trovato"""
        mock_ticket_repo.get_ticket_by_session.return_value = None

        result = ticket_service.get_ticket_by_session(456)

        assert result is None

    # ========== Test Close Ticket by Session (TU127) ==========

    @pytest.mark.asyncio
    async def test_close_ticket_by_session_success(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: close_ticket_by_session chiude il ticket della sessione"""
        # Setup
        session_id = 456
        mock_ticket_repo.get_ticket_by_session.return_value = {
            "id": 1,
            "session_id": session_id,
        }
        # close_ticket needs get_ticket_by_id
        mock_ticket_repo.get_ticket_by_id.return_value = {
            "id": 1,
            "session_id": session_id,
        }

        # Execute
        await ticket_service.close_ticket_by_session(session_id)

        # Verify
        mock_ticket_repo.close_ticket.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_close_ticket_by_session_not_found(self, ticket_service, mock_ticket_repo, mock_broadcaster):
        """Test: close_ticket_by_session non fa nulla se nessun ticket"""
        mock_ticket_repo.get_ticket_by_session.return_value = None

        # Execute — non dovrebbe sollevare eccezioni
        await ticket_service.close_ticket_by_session(456)

        # Verify
        mock_ticket_repo.close_ticket.assert_not_called()

    # ========== Test Save Customer Message (TU128) ==========

    @pytest.mark.asyncio
    async def test_save_customer_message_success(self, ticket_service, mock_db_adapter, mock_broadcaster):
        """Test: save_customer_message salva messaggio e notifica via SSE"""
        # Setup
        session_id = 456
        content = "Ho bisogno di aiuto"
        mock_db_adapter.send_message.return_value = 789

        # Execute
        result = await ticket_service.save_customer_message(session_id, content)

        # Verify
        assert result["id"] == 789
        assert result["sender"] == "user"
        assert result["content"] == content
        mock_db_adapter.send_message.assert_called_once_with(session_id, "user", content)
        # Emette su OPERATOR_CHANNEL e session_id
        assert mock_broadcaster.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_save_customer_message_no_broadcaster(self, mock_ticket_repo, mock_db_adapter):
        """Test: save_customer_message senza broadcaster non fallisce"""
        service = TicketService(mock_ticket_repo, mock_db_adapter, broadcaster=None)
        mock_db_adapter.send_message.return_value = 789

        result = await service.save_customer_message(456, "test")

        assert result["id"] == 789
        assert result["sender"] == "user"
>>>>>>> Stashed changes
