<<<<<<< Updated upstream
import pytest
from unittest.mock import Mock
from services.product_service import ProductService


class TestProductService:
    """Unit test per ProductService (ricerca prodotti)"""

    @pytest.fixture
    def mock_repo(self):
        """Mock del product repository"""
        return Mock()

    @pytest.fixture
    def product_service(self, mock_repo):
        """Istanza di ProductService con mock"""
        return ProductService(mock_repo)

    # ========== Test Search Products ==========

    def test_search_products_basic(self, product_service, mock_repo):
        """Test: search_products con query semplice"""
        # Setup
        query = "pasta"
        cod_cli = 100
        expected_products = [
            {"cod_art": "ART001", "des_art": "Pasta Integrale 500g", "prezzo": 2.50},
            {"cod_art": "ART002", "des_art": "Pasta Fresca 250g", "prezzo": 3.50},
        ]
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify
        assert result == expected_products
        mock_repo.search_products.assert_called_once_with(query, cod_cli, 20)

    def test_search_products_with_limit(self, product_service, mock_repo):
        """Test: search_products con limite custom"""
        # Setup
        query = "pane"
        cod_cli = 100
        limit = 50
        expected_products = [
            {"cod_art": f"ART{i}", "des_art": f"Pane Tipo {i}", "prezzo": 2.0}
            for i in range(1, 31)  # Simula 30 risultati
        ]
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli, limit=limit)
        
        # Verify
        assert result == expected_products
        mock_repo.search_products.assert_called_once_with(query, cod_cli, limit)

    def test_search_products_empty_query(self, product_service, mock_repo):
        """Test: search_products con query vuota"""
        # Setup
        query = ""
        cod_cli = 100
        expected_products = []
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify
        assert result == []

    def test_search_products_no_results(self, product_service, mock_repo):
        """Test: search_products che non trova risultati"""
        # Setup
        query = "non_esistente_xyz"
        cod_cli = 100
        mock_repo.search_products.return_value = []
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify
        assert result == []

    def test_search_products_special_characters(self, product_service, mock_repo):
        """Test: search_products con caratteri speciali nella query"""
        # Setup
        query = "pasta & pane"
        cod_cli = 100
        expected_products = [
            {"cod_art": "ART001", "des_art": "Pasta & Pane Mix", "prezzo": 5.00},
        ]
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify
        assert result == expected_products

    def test_search_products_case_insensitive(self, product_service, mock_repo):
        """Test: search_products case-insensitive"""
        # Setup - il service passa la query così com'è al repo
        # Il repo dovrebbe gestire la case-insensitivity
        query = "PASTA"
        cod_cli = 100
        expected_products = [
            {"cod_art": "ART001", "des_art": "Pasta Integrale", "prezzo": 2.50},
        ]
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify
        assert result == expected_products

    def test_search_products_different_clients(self, product_service, mock_repo):
        """Test: search_products rispetta il cliente (assortimento)"""
        # Setup
        query = "pasta"
        cod_cli_1 = 100
        cod_cli_2 = 101
        
        products_cli_1 = [
            {"cod_art": "ART001", "des_art": "Pasta A", "prezzo": 2.50},
        ]
        products_cli_2 = [
            {"cod_art": "ART002", "des_art": "Pasta B", "prezzo": 3.50},
        ]
        
        # Mock returns different results based on client
        mock_repo.search_products.side_effect = [products_cli_1, products_cli_2]
        
        # Execute
        result_1 = product_service.search_products(query, cod_cli_1)
        result_2 = product_service.search_products(query, cod_cli_2)
        
        # Verify
        assert result_1 == products_cli_1
        assert result_2 == products_cli_2
        assert result_1 != result_2

    def test_search_products_returns_correct_columns(self, product_service, mock_repo):
        """Test: search_products ritorna i campi corretti"""
        # Setup
        query = "test"
        cod_cli = 100
        expected_products = [
            {
                "cod_art": "ART001",
                "des_art": "Test Product",
                "prezzo": 10.00,
                "unita_vendita": "pz",
                "costo_unitario": 8.00,
            }
        ]
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify - controlla che tutti i campi siano presenti
        assert len(result) == 1
        product = result[0]
        assert "cod_art" in product
        assert "des_art" in product
        assert "prezzo" in product
=======
import pytest
from unittest.mock import Mock
from services.product_service import ProductService


class TestProductService:
    """Unit test per ProductService (ricerca prodotti)"""

    @pytest.fixture
    def mock_repo(self):
        """Mock del product repository"""
        return Mock()

    @pytest.fixture
    def product_service(self, mock_repo):
        """Istanza di ProductService con mock"""
        return ProductService(mock_repo)

    # ========== Test Search Products ==========

    def test_search_products_basic(self, product_service, mock_repo):
        """Test: search_products con query semplice"""
        # Setup
        query = "pasta"
        cod_cli = 100
        expected_products = [
            {"cod_art": "ART001", "des_art": "Pasta Integrale 500g", "prezzo": 2.50},
            {"cod_art": "ART002", "des_art": "Pasta Fresca 250g", "prezzo": 3.50},
        ]
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify
        assert result == expected_products
        mock_repo.search_products.assert_called_once_with(query, cod_cli, 20)

    def test_search_products_with_limit(self, product_service, mock_repo):
        """Test: search_products con limite custom"""
        # Setup
        query = "pane"
        cod_cli = 100
        limit = 50
        expected_products = [
            {"cod_art": f"ART{i}", "des_art": f"Pane Tipo {i}", "prezzo": 2.0}
            for i in range(1, 31)  # Simula 30 risultati
        ]
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli, limit=limit)
        
        # Verify
        assert result == expected_products
        mock_repo.search_products.assert_called_once_with(query, cod_cli, limit)

    def test_search_products_empty_query(self, product_service, mock_repo):
        """Test: search_products con query vuota"""
        # Setup
        query = ""
        cod_cli = 100
        expected_products = []
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify
        assert result == []

    def test_search_products_no_results(self, product_service, mock_repo):
        """Test: search_products che non trova risultati"""
        # Setup
        query = "non_esistente_xyz"
        cod_cli = 100
        mock_repo.search_products.return_value = []
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify
        assert result == []

    def test_search_products_special_characters(self, product_service, mock_repo):
        """Test: search_products con caratteri speciali nella query"""
        # Setup
        query = "pasta & pane"
        cod_cli = 100
        expected_products = [
            {"cod_art": "ART001", "des_art": "Pasta & Pane Mix", "prezzo": 5.00},
        ]
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify
        assert result == expected_products

    def test_search_products_case_insensitive(self, product_service, mock_repo):
        """Test: search_products case-insensitive"""
        # Setup - il service passa la query così com'è al repo
        # Il repo dovrebbe gestire la case-insensitivity
        query = "PASTA"
        cod_cli = 100
        expected_products = [
            {"cod_art": "ART001", "des_art": "Pasta Integrale", "prezzo": 2.50},
        ]
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify
        assert result == expected_products

    def test_search_products_different_clients(self, product_service, mock_repo):
        """Test: search_products rispetta il cliente (assortimento)"""
        # Setup
        query = "pasta"
        cod_cli_1 = 100
        cod_cli_2 = 101
        
        products_cli_1 = [
            {"cod_art": "ART001", "des_art": "Pasta A", "prezzo": 2.50},
        ]
        products_cli_2 = [
            {"cod_art": "ART002", "des_art": "Pasta B", "prezzo": 3.50},
        ]
        
        # Mock returns different results based on client
        mock_repo.search_products.side_effect = [products_cli_1, products_cli_2]
        
        # Execute
        result_1 = product_service.search_products(query, cod_cli_1)
        result_2 = product_service.search_products(query, cod_cli_2)
        
        # Verify
        assert result_1 == products_cli_1
        assert result_2 == products_cli_2
        assert result_1 != result_2

    def test_search_products_returns_correct_columns(self, product_service, mock_repo):
        """Test: search_products ritorna i campi corretti"""
        # Setup
        query = "test"
        cod_cli = 100
        expected_products = [
            {
                "cod_art": "ART001",
                "des_art": "Test Product",
                "prezzo": 10.00,
                "unita_vendita": "pz",
                "costo_unitario": 8.00,
            }
        ]
        mock_repo.search_products.return_value = expected_products
        
        # Execute
        result = product_service.search_products(query, cod_cli)
        
        # Verify - controlla che tutti i campi siano presenti
        assert len(result) == 1
        product = result[0]
        assert "cod_art" in product
        assert "des_art" in product
        assert "prezzo" in product
>>>>>>> Stashed changes
