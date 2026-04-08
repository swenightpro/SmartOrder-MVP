import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch, mock_open
from services.order_service import OrderService


class TestOrderService:
    """Unit test per OrderService (ordini)"""

    @pytest.fixture
    def mock_order_repo(self):
        """Mock del repository ordini"""
        return Mock()

    @pytest.fixture
    def mock_session_manager(self):
        """Mock del session manager"""
        return Mock()

    @pytest.fixture
    def mock_broadcaster(self):
        """Mock del broadcaster SSE con coroutine async"""
        mock = Mock()
        mock.emit = AsyncMock()  # emit() ritorna una coroutine valida
        return mock

    @pytest.fixture
    def order_service(self, mock_order_repo, mock_session_manager, mock_broadcaster):
        """Istanza di OrderService con mock"""
        return OrderService(mock_order_repo, mock_session_manager, mock_broadcaster)

    # ========== Test Create Order ==========

    def test_create_order_success(self, order_service, mock_order_repo, mock_session_manager):
        """Test: create_order crea ordine con successo"""
        # Setup
        cod_cli = 100
        user_id = 123
        session_id = 456
        items = [
            {"cod_art": "ART001", "qta": 5},
            {"cod_art": "ART002", "qta": 3},
        ]
        expected_order_id = 789
        
        mock_order_repo.create_order.return_value = expected_order_id
        mock_session_manager.clear_cart_by_session.return_value = None
        
        # Execute
        result = order_service.create_order(cod_cli, user_id, session_id, items)
        
        # Verify
        assert result == expected_order_id
        mock_order_repo.create_order.assert_called_once_with(
            cod_cli, user_id, session_id, items
        )
        # Verifica che il carrello sia stato svuotato
        mock_session_manager.clear_cart_by_session.assert_called_once_with(session_id)

    def test_create_order_clears_cart(self, order_service, mock_order_repo, mock_session_manager):
        """Test: create_order svuota il carrello dopo creazione"""
        # Setup
        cod_cli = 100
        user_id = 123
        session_id = None  # Usa user_id invece di session_id
        items = [
            {"cod_art": "ART001", "qta": 5},
        ]
        expected_order_id = 789
        
        mock_order_repo.create_order.return_value = expected_order_id
        mock_session_manager.clear_cart.return_value = None
        
        # Execute
        result = order_service.create_order(cod_cli, user_id, session_id, items)
        
        # Verify
        assert result == expected_order_id
        # Quando session_id è None, chiama clear_cart(user_id)
        mock_session_manager.clear_cart.assert_called_once_with(user_id)

    def test_create_order_empty_items(self, order_service, mock_order_repo, mock_session_manager):
        """Test: create_order con lista articoli vuota"""
        # Setup
        cod_cli = 100
        user_id = 123
        session_id = 456
        items = []  # Lista vuota
        expected_order_id = 789
        
        mock_order_repo.create_order.return_value = expected_order_id
        
        # Execute
        result = order_service.create_order(cod_cli, user_id, session_id, items)
        
        # Verify - il service crea comunque l'ordine
        assert result == expected_order_id

    # ========== Test Get Orders by Client ==========

    def test_get_orders_by_client(self, order_service, mock_order_repo):
        """Test: get_orders_by_client ritorna ordini del cliente"""
        # Setup
        cod_cli = 100
        expected_orders = [
            {"id": 1, "cod_cli": cod_cli, "data_ord": "2026-04-01"},
            {"id": 2, "cod_cli": cod_cli, "data_ord": "2026-04-02"},
        ]
        mock_order_repo.get_orders_by_client.return_value = expected_orders
        
        # Execute
        result = order_service.get_orders_by_client(cod_cli)
        
        # Verify
        assert result == expected_orders
        mock_order_repo.get_orders_by_client.assert_called_once()

    def test_get_orders_by_client_with_pagination(self, order_service, mock_order_repo):
        """Test: get_orders_by_client con paginazione"""
        # Setup
        cod_cli = 100
        page = 2
        limit = 10
        expected_orders = [
            {"id": 21, "cod_cli": cod_cli},
            {"id": 22, "cod_cli": cod_cli},
        ]
        mock_order_repo.get_orders_by_client.return_value = expected_orders
        
        # Execute
        result = order_service.get_orders_by_client(
            cod_cli, page=page, limit=limit
        )
        
        # Verify
        assert result == expected_orders
        mock_order_repo.get_orders_by_client.assert_called_once()

    def test_get_orders_by_client_with_search(self, order_service, mock_order_repo):
        """Test: get_orders_by_client con ricerca"""
        # Setup
        cod_cli = 100
        search = "ART001"
        expected_orders = [
            {"id": 1, "cod_cli": cod_cli, "items": [{"cod_art": "ART001"}]},
        ]
        mock_order_repo.get_orders_by_client.return_value = expected_orders
        
        # Execute
        result = order_service.get_orders_by_client(cod_cli, search=search)
        
        # Verify
        assert result == expected_orders

    def test_get_orders_by_client_with_date_filter(self, order_service, mock_order_repo):
        """Test: get_orders_by_client con filtro date"""
        # Setup
        cod_cli = 100
        date_from = "2026-04-01"
        date_to = "2026-04-30"
        expected_orders = [
            {"id": 1, "cod_cli": cod_cli, "data_ord": "2026-04-15"},
        ]
        mock_order_repo.get_orders_by_client.return_value = expected_orders
        
        # Execute
        result = order_service.get_orders_by_client(
            cod_cli,
            date_from=date_from,
            date_to=date_to
        )
        
        # Verify
        assert result == expected_orders

    def test_get_orders_by_client_with_sort(self, order_service, mock_order_repo):
        """Test: get_orders_by_client con ordinamento"""
        # Setup
        cod_cli = 100
        expected_orders = [
            {"id": 2, "cod_cli": cod_cli, "data_ord": "2026-04-02"},
            {"id": 1, "cod_cli": cod_cli, "data_ord": "2026-04-01"},
        ]
        mock_order_repo.get_orders_by_client.return_value = expected_orders
        
        # Execute
        result = order_service.get_orders_by_client(
            cod_cli,
            sort_by="data_ord",
            sort_dir="desc"
        )
        
        # Verify
        assert result == expected_orders

    def test_get_orders_by_client_empty(self, order_service, mock_order_repo):
        """Test: get_orders_by_client ritorna lista vuota se non ci sono ordini"""
        # Setup
        cod_cli = 100
        mock_order_repo.get_orders_by_client.return_value = []
        
        # Execute
        result = order_service.get_orders_by_client(cod_cli)
        
        # Verify
        assert result == []

    # ========== Test Get All Orders (Operator) ==========

    def test_get_all_orders(self, order_service, mock_order_repo):
        """Test: get_all_orders per operatore ritorna tutti gli ordini"""
        # Setup
        expected_orders = [
            {"id": 1, "cod_cli": 100, "rag_soc": "Company A"},
            {"id": 2, "cod_cli": 101, "rag_soc": "Company B"},
        ]
        mock_order_repo.get_all_orders.return_value = expected_orders
        
        # Execute
        result = order_service.get_all_orders()
        
        # Verify
        assert result == expected_orders
        mock_order_repo.get_all_orders.assert_called_once()

    def test_get_all_orders_with_client_filter(self, order_service, mock_order_repo):
        """Test: get_all_orders con filtro cliente"""
        # Setup
        search_cod_cli = "100"
        expected_orders = [
            {"id": 1, "cod_cli": 100, "rag_soc": "Company A"},
        ]
        mock_order_repo.get_all_orders.return_value = expected_orders
        
        # Execute
        result = order_service.get_all_orders(search_cod_cli=search_cod_cli)
        
        # Verify
        assert result == expected_orders

    def test_get_all_orders_with_esportato_filter(self, order_service, mock_order_repo):
        """Test: get_all_orders filtering ordini esportati"""
        # Setup
        expected_orders = [
            {"id": 1, "cod_cli": 100, "esportato": True},
        ]
        mock_order_repo.get_all_orders.return_value = expected_orders
        
        # Execute
        result = order_service.get_all_orders(esportato=True)
        
        # Verify
        assert result == expected_orders

    # ========== Test Get Order Detail ==========

    def test_get_order_detail_success(self, order_service, mock_order_repo):
        """Test: get_order_detail ritorna dettagli ordine"""
        # Setup
        order_id = 1
        cod_cli = 100
        expected_detail = {
            "id": order_id,
            "cod_cli": cod_cli,
            "items": [
                {"cod_art": "ART001", "qta": 5},
            ],
            "data_ord": "2026-04-01",
        }
        mock_order_repo.get_order_detail.return_value = expected_detail
        
        # Execute
        result = order_service.get_order_detail(order_id, cod_cli)
        
        # Verify
        assert result == expected_detail
        mock_order_repo.get_order_detail.assert_called_once_with(order_id, cod_cli)

    def test_get_order_detail_not_found(self, order_service, mock_order_repo):
        """Test: get_order_detail ritorna None se ordine non trovato"""
        # Setup
        order_id = 999
        cod_cli = 100
        mock_order_repo.get_order_detail.return_value = None

        # Execute
        result = order_service.get_order_detail(order_id, cod_cli)

        # Verify
        assert result is None

    # ========== Test Export Order (TU133) ==========

    def test_export_order_json_success(self, order_service, mock_order_repo):
        """Test: export_order esporta ordine in JSON"""
        # Setup
        user_id = 123
        order_id = 1
        mock_order_repo.get_export_folder.return_value = "/tmp/test_export"
        mock_order_repo.get_order_detail_any.return_value = {
            "id": order_id,
            "data_ord": "2026-04-01",
            "items": [{"cod_art": "ART001", "qta_ordinata": 5}],
        }

        # Execute
        with patch("os.makedirs"), \
             patch("builtins.open", mock_open()):
            result = order_service.export_order(order_id, user_id, fmt="json")

        # Verify
        assert result is not None
        assert result["format"] == "json"
        assert "file_path" in result
        assert "filename" in result
        mock_order_repo.mark_order_exported.assert_called_once_with(order_id)

    def test_export_order_not_found(self, order_service, mock_order_repo):
        """Test: export_order ritorna None se ordine non esiste"""
        mock_order_repo.get_export_folder.return_value = "/tmp/export"
        mock_order_repo.get_order_detail_any.return_value = None

        result = order_service.export_order(999, 123)

        assert result is None

    def test_export_order_no_folder(self, order_service, mock_order_repo):
        """Test: export_order solleva errore senza cartella configurata"""
        mock_order_repo.get_export_folder.return_value = None

        with pytest.raises(ValueError, match="non configurata"):
            order_service.export_order(1, 123)

    def test_export_order_csv_success(self, order_service, mock_order_repo):
        """Test: export_order esporta ordine in CSV"""
        mock_order_repo.get_export_folder.return_value = "/tmp/test_export"
        mock_order_repo.get_order_detail_any.return_value = {
            "id": 1,
            "data_ord": "2026-04-01",
            "items": [{"cod_art": "ART001", "des_art": "Pasta", "qta_ordinata": 5}],
        }

        with patch("os.makedirs"), \
             patch("builtins.open", mock_open()):
            result = order_service.export_order(1, 123, fmt="csv")

        assert result is not None
        assert result["format"] == "csv"

    # ========== Test Export Batch (TU134) ==========

    def test_export_batch_success(self, order_service, mock_order_repo):
        """Test: export_batch esporta più ordini non esportati"""
        # Setup
        mock_order_repo.get_export_folder.return_value = "/tmp/test_export"
        mock_order_repo.get_all_orders.return_value = [
            {"order_id": 1},
            {"order_id": 2},
        ]
        mock_order_repo.get_order_detail_any.side_effect = [
            {"id": 1, "data_ord": "2026-04-01", "items": []},
            {"id": 2, "data_ord": "2026-04-02", "items": []},
        ]

        with patch("os.makedirs"), \
             patch("builtins.open", mock_open()):
            result = order_service.export_batch(user_id=123)

        # Verify
        assert result["exported_count"] == 2
        assert result["failed_count"] == 0
        assert result["errors"] == []
        mock_order_repo.mark_orders_exported.assert_called_once_with([1, 2])

    def test_export_batch_no_folder(self, order_service, mock_order_repo):
        """Test: export_batch solleva errore senza cartella"""
        mock_order_repo.get_export_folder.return_value = None

        with pytest.raises(ValueError, match="non configurata"):
            order_service.export_batch(user_id=123)

    def test_export_batch_partial_failure(self, order_service, mock_order_repo):
        """Test: export_batch gestisce errori parziali"""
        mock_order_repo.get_export_folder.return_value = "/tmp/test_export"
        mock_order_repo.get_all_orders.return_value = [
            {"order_id": 1},
            {"order_id": 2},
        ]
        mock_order_repo.get_order_detail_any.side_effect = [
            {"id": 1, "data_ord": "2026-04-01", "items": []},
            None,  # Ordine 2 non trovato
        ]

        with patch("os.makedirs"), \
             patch("builtins.open", mock_open()):
            result = order_service.export_batch(user_id=123)

        assert result["exported_count"] == 1
        assert result["failed_count"] == 1
        assert len(result["errors"]) == 1

    def test_export_batch_empty(self, order_service, mock_order_repo):
        """Test: export_batch senza ordini da esportare"""
        mock_order_repo.get_export_folder.return_value = "/tmp/test_export"
        mock_order_repo.get_all_orders.return_value = []

        result = order_service.export_batch(user_id=123)

        assert result["exported_count"] == 0
        assert result["failed_count"] == 0
