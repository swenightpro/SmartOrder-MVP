import pytest
from unittest.mock import Mock
from services.client_service import ClientService


class TestClientService:
    """Unit test per ClientService (ricerca clienti)"""

    @pytest.fixture
    def mock_repo(self):
        """Mock del client repository"""
        return Mock()

    @pytest.fixture
    def client_service(self, mock_repo):
        """Istanza di ClientService con mock"""
        return ClientService(mock_repo)

    # ========== Test Search Clients ==========

    def test_search_clients_basic(self, client_service, mock_repo):
        """Test: search_clients con query semplice"""
        # Setup
        query = "Company A"
        limit = 10
        expected_clients = [
            {
                "cod_cli": 100,
                "rag_soc": "Company A",
                "citta": "Milano",
            },
            {
                "cod_cli": 101,
                "rag_soc": "Company A Italia",
                "citta": "Roma",
            },
        ]
        mock_repo.search_clients.return_value = expected_clients
        
        # Execute
        result = client_service.search_clients(query, limit)
        
        # Verify
        assert result == expected_clients
        mock_repo.search_clients.assert_called_once_with(query, limit)

    def test_search_clients_default_limit(self, client_service, mock_repo):
        """Test: search_clients usa limit di default (10)"""
        # Setup
        query = "test"
        expected_clients = []
        mock_repo.search_clients.return_value = expected_clients
        
        # Execute
        result = client_service.search_clients(query)
        
        # Verify
        assert result == expected_clients
        # Verifica che il limit di default sia 10
        mock_repo.search_clients.assert_called_once_with(query, 10)

    def test_search_clients_custom_limit(self, client_service, mock_repo):
        """Test: search_clients con limit custom"""
        # Setup
        query = "Client"
        custom_limit = 50
        expected_clients = [
            {"cod_cli": i, "rag_soc": f"Client {i}"}
            for i in range(1, 31)  # 30 clienti
        ]
        mock_repo.search_clients.return_value = expected_clients
        
        # Execute
        result = client_service.search_clients(query, limit=custom_limit)
        
        # Verify
        assert result == expected_clients
        mock_repo.search_clients.assert_called_once_with(query, custom_limit)

    def test_search_clients_empty_query(self, client_service, mock_repo):
        """Test: search_clients con query vuota"""
        # Setup
        query = ""
        expected_clients = []
        mock_repo.search_clients.return_value = expected_clients
        
        # Execute
        result = client_service.search_clients(query)
        
        # Verify
        assert result == []

    def test_search_clients_no_results(self, client_service, mock_repo):
        """Test: search_clients che non trova clienti"""
        # Setup
        query = "non_esiste_xyz"
        mock_repo.search_clients.return_value = []
        
        # Execute
        result = client_service.search_clients(query)
        
        # Verify
        assert result == []

    def test_search_clients_by_code(self, client_service, mock_repo):
        """Test: search_clients per codice cliente"""
        # Setup
        query = "100"  # Codice cliente
        expected_clients = [
            {
                "cod_cli": 100,
                "rag_soc": "Company A",
            }
        ]
        mock_repo.search_clients.return_value = expected_clients
        
        # Execute
        result = client_service.search_clients(query)
        
        # Verify
        assert result == expected_clients

    def test_search_clients_returns_full_data(self, client_service, mock_repo):
        """Test: search_clients ritorna dati completi del cliente"""
        # Setup
        query = "test"
        expected_clients = [
            {
                "cod_cli": 100,
                "rag_soc": "Test Company",
                "indirizzo": "Via Roma 123",
                "citta": "Milano",
                "cap": "20100",
                "provincia": "MI",
            }
        ]
        mock_repo.search_clients.return_value = expected_clients
        
        # Execute
        result = client_service.search_clients(query)
        
        # Verify
        assert len(result) == 1
        client = result[0]
        assert client["cod_cli"] == 100
        assert client["rag_soc"] == "Test Company"
        assert "indirizzo" in client
        assert "citta" in client