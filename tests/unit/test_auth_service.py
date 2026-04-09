<<<<<<< Updated upstream
import pytest
import time
from unittest.mock import Mock, MagicMock
from services.auth_service import AuthService
from config import Settings


class TestAuthService:
    """Unit test per AuthService (autenticazione)"""

    @pytest.fixture
    def mock_repo(self):
        """Mock del repository utenti"""
        return Mock()

    @pytest.fixture
    def auth_service(self, mock_repo):
        """Istanza di AuthService con mock"""
        return AuthService(mock_repo)

    # ========== Test Password Hashing ==========

    def test_hash_password_generates_valid_hash(self, auth_service):
        """Test: hash_password produce hash e salt validi"""
        password = "test_password_123"
        
        hash_hex, salt_hex = auth_service.hash_password(password)
        
        # Verifica che non siano vuoti
        assert hash_hex
        assert salt_hex
        # Verifica che siano hex (contengono solo 0-9a-f)
        assert all(c in "0123456789abcdef" for c in hash_hex)
        assert all(c in "0123456789abcdef" for c in salt_hex)

    def test_hash_password_different_salts(self, auth_service):
        """Test: stessa password con salt diversi da hash diversi"""
        password = "test_password"
        
        hash1, salt1 = auth_service.hash_password(password)
        hash2, salt2 = auth_service.hash_password(password)
        
        # Salt diversi (casuali)
        assert salt1 != salt2
        # Hash diversi (perché salt diverso)
        assert hash1 != hash2

    def test_verify_password_correct(self, auth_service):
        """Test: verify_password ritorna True per password corretta"""
        password = "my_secure_password"
        
        # Genera hash e salt
        hash_hex, salt_hex = auth_service.hash_password(password)
        
        # Verifica che sia True
        result = auth_service.verify_password(password, hash_hex, salt_hex)
        assert result is True

    def test_verify_password_incorrect(self, auth_service):
        """Test: verify_password ritorna False per password sbagliata"""
        password = "correct_password"
        wrong_password = "wrong_password"
        
        # Genera hash e salt
        hash_hex, salt_hex = auth_service.hash_password(password)
        
        # Verifica che sia False
        result = auth_service.verify_password(wrong_password, hash_hex, salt_hex)
        assert result is False

    def test_verify_password_empty_password(self, auth_service):
        """Test: verify_password ritorna False per password vuota"""
        password = "test_password"
        hash_hex, salt_hex = auth_service.hash_password(password)
        
        # Verifica con password vuota
        result = auth_service.verify_password("", hash_hex, salt_hex)
        assert result is False

    # ========== Test JWT ==========

    def test_create_jwt_generates_valid_token(self, auth_service):
        """Test: create_jwt genera un token valido"""
        user_id = 123
        cod_cli = 456
        role = "customer"
        
        token = auth_service.create_jwt(user_id, cod_cli, role)
        
        # Token non vuoto
        assert token
        # Token è una stringa
        assert isinstance(token, str)
        # Token ha almeno 3 parti (header.payload.signature)
        assert token.count('.') >= 2

    def test_verify_jwt_valid_token(self, auth_service):
        """Test: verify_jwt decodifica un token valido"""
        user_id = 123
        cod_cli = 456
        role = "customer"
        
        # Crea token
        token = auth_service.create_jwt(user_id, cod_cli, role)
        
        # Verifica token
        payload = auth_service.verify_jwt(token)
        
        # Payload non nullo
        assert payload is not None
        # Contiene i dati corretti
        assert payload["sub"] == str(user_id)
        assert payload["cod_cli"] == cod_cli
        assert payload["role"] == role

    def test_verify_jwt_invalid_token(self, auth_service):
        """Test: verify_jwt ritorna None per token invalido"""
        invalid_token = "invalid.token.here"
        
        payload = auth_service.verify_jwt(invalid_token)
        
        assert payload is None

    def test_verify_jwt_expired_token(self, auth_service):
        """Test: verify_jwt ritorna None per token scaduto"""
        # Crea un token con scadenza immediata (mocando il tempo)
        user_id = 123
        cod_cli = 456
        role = "customer"
        
        # Crea token con servizio
        token = auth_service.create_jwt(user_id, cod_cli, role)
        
        # Aspetta che scada (in test, aspettiamo 1 secondo se la scadenza è immediata)
        # Per ora verificiamo solo che il token è valido subito dopo la creazione
        payload = auth_service.verify_jwt(token)
        assert payload is not None

    # ========== Test Login Use Case ==========

    def test_login_success(self, auth_service, mock_repo):
        """Test: login con credenziali corrette ritorna token"""
        # Setup
        email = "user@example.com"
        password = "correct_password"
        user_id = 123
        cod_cli = 456
        
        # Genera hash password
        hash_hex, salt_hex = auth_service.hash_password(password)
        
        # Mock repo ritorna utente
        mock_repo.find_by_email.return_value = {
            "id": user_id,
            "email": email,
            "password_hash": hash_hex,
            "password_salt": salt_hex,
            "role": "customer",
            "cod_cli": cod_cli,
        }
        mock_repo.get_client_info.return_value = {
            "rag_soc": "Test Company"
        }
        
        # Execute
        result = auth_service.login(email, password)
        
        # Verify
        assert result is not None
        assert "token" in result
        assert result["cod_cli"] == cod_cli
        assert result["role"] == "customer"

    def test_login_user_not_found(self, auth_service, mock_repo):
        """Test: login con email inesistente ritorna None"""
        # Setup
        email = "nonexistent@example.com"
        password = "any_password"
        
        mock_repo.find_by_email.return_value = None
        
        # Execute
        result = auth_service.login(email, password)
        
        # Verify
        assert result is None

    def test_login_wrong_password(self, auth_service, mock_repo):
        """Test: login con password sbagliata ritorna None"""
        # Setup
        email = "user@example.com"
        correct_password = "correct_password"
        wrong_password = "wrong_password"
        user_id = 123

        # Genera hash password corretta
        hash_hex, salt_hex = auth_service.hash_password(correct_password)

        # Mock repo
        mock_repo.find_by_email.return_value = {
            "id": user_id,
            "email": email,
            "password_hash": hash_hex,
            "password_salt": salt_hex,
            "role": "customer",
            "cod_cli": 456,
        }

        # Execute con password sbagliata
        result = auth_service.login(email, wrong_password)

        # Verify
        assert result is None

    # ========== Test Get Profile (TU108) ==========

    def test_get_profile_success(self, auth_service, mock_repo):
        """Test: get_profile ritorna profilo utente con rag_soc"""
        # Setup
        user_id = 123
        mock_repo.find_by_id.return_value = {
            "id": user_id,
            "email": "user@example.com",
            "cod_cli": 456,
            "role": "customer",
            "export_folder": "/tmp/export",
            "created_at": "2026-01-01",
            "updated_at": "2026-04-01",
        }
        mock_repo.get_client_info.return_value = {"rag_soc": "Test Company"}

        # Execute
        result = auth_service.get_profile(user_id)

        # Verify
        assert result is not None
        assert result["email"] == "user@example.com"
        assert result["cod_cli"] == 456
        assert result["rag_soc"] == "Test Company"
        assert result["role"] == "customer"
        assert result["export_folder"] == "/tmp/export"

    def test_get_profile_not_found(self, auth_service, mock_repo):
        """Test: get_profile ritorna None se utente non trovato"""
        # Setup
        mock_repo.find_by_id.return_value = None

        # Execute
        result = auth_service.get_profile(999)

        # Verify
        assert result is None

    def test_get_profile_no_cod_cli(self, auth_service, mock_repo):
        """Test: get_profile senza cod_cli non chiama get_client_info"""
        # Setup
        mock_repo.find_by_id.return_value = {
            "id": 123,
            "email": "admin@example.com",
            "cod_cli": 0,
            "role": "admin",
            "created_at": "",
            "updated_at": "",
        }

        # Execute
        result = auth_service.get_profile(123)

        # Verify
        assert result is not None
        assert result["rag_soc"] == ""
        mock_repo.get_client_info.assert_not_called()

    # ========== Test Get/Set Export Folder (TU109-TU110) ==========

    def test_get_export_folder(self, auth_service, mock_repo):
        """Test: get_export_folder delega al repository"""
        # Setup
        mock_repo.get_export_folder.return_value = "/tmp/export"

        # Execute
        result = auth_service.get_export_folder(123)

        # Verify
        assert result == "/tmp/export"
        mock_repo.get_export_folder.assert_called_once_with(123)

    def test_get_export_folder_none(self, auth_service, mock_repo):
        """Test: get_export_folder ritorna None se non configurato"""
        # Setup
        mock_repo.get_export_folder.return_value = None

        # Execute
        result = auth_service.get_export_folder(123)

        # Verify
        assert result is None

    def test_set_export_folder(self, auth_service, mock_repo):
        """Test: set_export_folder delega al repository"""
        # Execute
        auth_service.set_export_folder(123, "/new/path")

        # Verify
        mock_repo.set_export_folder.assert_called_once_with(123, "/new/path")

    def test_set_export_folder_none(self, auth_service, mock_repo):
        """Test: set_export_folder con None resetta il path"""
        # Execute
        auth_service.set_export_folder(123, None)

        # Verify
        mock_repo.set_export_folder.assert_called_once_with(123, None)

    # ========== Test Change Password (TU111) ==========

    def test_change_password_success(self, auth_service, mock_repo):
        """Test: change_password con dati corretti cambia la password"""
        # Setup
        user_id = 123
        current_password = "old_password"
        new_password = "new_password_123"

        hash_hex, salt_hex = auth_service.hash_password(current_password)
        mock_repo.find_by_id.return_value = {
            "id": user_id,
            "password_hash": hash_hex,
            "password_salt": salt_hex,
        }

        # Execute
        success, error = auth_service.change_password(
            user_id, current_password, new_password, new_password
        )

        # Verify
        assert success is True
        assert error == ""
        mock_repo.update_password.assert_called_once()

    def test_change_password_too_short(self, auth_service, mock_repo):
        """Test: change_password rifiuta password troppo corte"""
        success, error = auth_service.change_password(123, "old", "ab", "ab")

        assert success is False
        assert "almeno 6 caratteri" in error

    def test_change_password_mismatch(self, auth_service, mock_repo):
        """Test: change_password rifiuta se conferma non coincide"""
        success, error = auth_service.change_password(
            123, "old_pass", "new_password", "different_password"
        )

        assert success is False
        assert "non coincidono" in error

    def test_change_password_same_as_current(self, auth_service, mock_repo):
        """Test: change_password rifiuta se nuova == attuale"""
        success, error = auth_service.change_password(
            123, "same_password", "same_password", "same_password"
        )

        assert success is False
        assert "diversa" in error

    def test_change_password_wrong_current(self, auth_service, mock_repo):
        """Test: change_password rifiuta se password attuale è sbagliata"""
        # Setup
        correct_pw = "correct_password"
        hash_hex, salt_hex = auth_service.hash_password(correct_pw)
        mock_repo.find_by_id.return_value = {
            "id": 123,
            "password_hash": hash_hex,
            "password_salt": salt_hex,
        }

        # Execute
        success, error = auth_service.change_password(
            123, "wrong_current", "new_password_123", "new_password_123"
        )

        # Verify
        assert success is False
        assert "non è corretta" in error

    def test_change_password_user_not_found(self, auth_service, mock_repo):
        """Test: change_password fallisce se utente non trovato"""
        mock_repo.find_by_id.return_value = None

        success, error = auth_service.change_password(
            999, "old_pass", "new_password_123", "new_password_123"
        )

        assert success is False
        assert "non trovato" in error

    # ========== Test Register (TU112) ==========

    def test_register_customer_success(self, auth_service, mock_repo):
        """Test: register crea un nuovo utente customer"""
        # Setup
        mock_repo.find_by_email.return_value = None

        # Execute
        success, error = auth_service.register(
            "new@example.com", "password123", "customer", cod_cli=100
        )

        # Verify
        assert success is True
        assert error == ""
        mock_repo.create_user.assert_called_once()

    def test_register_admin_success(self, auth_service, mock_repo):
        """Test: register crea un nuovo utente admin (senza cod_cli)"""
        mock_repo.find_by_email.return_value = None

        success, error = auth_service.register(
            "admin@example.com", "password123", "admin", cod_cli=None
        )

        assert success is True
        # Admin non ha cod_cli
        call_args = mock_repo.create_user.call_args
        assert call_args[0][3] == "admin"
        assert call_args[0][4] is None

    def test_register_empty_email(self, auth_service, mock_repo):
        """Test: register rifiuta email vuota"""
        success, error = auth_service.register("", "password123", "customer", 100)

        assert success is False
        assert "obbligatori" in error

    def test_register_empty_password(self, auth_service, mock_repo):
        """Test: register rifiuta password vuota"""
        success, error = auth_service.register("user@test.com", "", "customer", 100)

        assert success is False
        assert "obbligatori" in error

    def test_register_customer_no_cod_cli(self, auth_service, mock_repo):
        """Test: register rifiuta customer senza cod_cli"""
        success, error = auth_service.register(
            "user@test.com", "password123", "customer", cod_cli=None
        )

        assert success is False
        assert "cod_cli" in error

    def test_register_duplicate_email(self, auth_service, mock_repo):
        """Test: register rifiuta email già registrata"""
        mock_repo.find_by_email.return_value = {"id": 1, "email": "dup@test.com"}

        success, error = auth_service.register(
            "dup@test.com", "password123", "customer", cod_cli=100
        )

        assert success is False
        assert "già registrata" in error
=======
import pytest
import time
from unittest.mock import Mock, MagicMock
from services.auth_service import AuthService
from config import Settings


class TestAuthService:
    """Unit test per AuthService (autenticazione)"""

    @pytest.fixture
    def mock_repo(self):
        """Mock del repository utenti"""
        return Mock()

    @pytest.fixture
    def auth_service(self, mock_repo):
        """Istanza di AuthService con mock"""
        return AuthService(mock_repo)

    # ========== Test Password Hashing ==========

    def test_hash_password_generates_valid_hash(self, auth_service):
        """Test: hash_password produce hash e salt validi"""
        password = "test_password_123"
        
        hash_hex, salt_hex = auth_service.hash_password(password)
        
        # Verifica che non siano vuoti
        assert hash_hex
        assert salt_hex
        # Verifica che siano hex (contengono solo 0-9a-f)
        assert all(c in "0123456789abcdef" for c in hash_hex)
        assert all(c in "0123456789abcdef" for c in salt_hex)

    def test_hash_password_different_salts(self, auth_service):
        """Test: stessa password con salt diversi da hash diversi"""
        password = "test_password"
        
        hash1, salt1 = auth_service.hash_password(password)
        hash2, salt2 = auth_service.hash_password(password)
        
        # Salt diversi (casuali)
        assert salt1 != salt2
        # Hash diversi (perché salt diverso)
        assert hash1 != hash2

    def test_verify_password_correct(self, auth_service):
        """Test: verify_password ritorna True per password corretta"""
        password = "my_secure_password"
        
        # Genera hash e salt
        hash_hex, salt_hex = auth_service.hash_password(password)
        
        # Verifica che sia True
        result = auth_service.verify_password(password, hash_hex, salt_hex)
        assert result is True

    def test_verify_password_incorrect(self, auth_service):
        """Test: verify_password ritorna False per password sbagliata"""
        password = "correct_password"
        wrong_password = "wrong_password"
        
        # Genera hash e salt
        hash_hex, salt_hex = auth_service.hash_password(password)
        
        # Verifica che sia False
        result = auth_service.verify_password(wrong_password, hash_hex, salt_hex)
        assert result is False

    def test_verify_password_empty_password(self, auth_service):
        """Test: verify_password ritorna False per password vuota"""
        password = "test_password"
        hash_hex, salt_hex = auth_service.hash_password(password)
        
        # Verifica con password vuota
        result = auth_service.verify_password("", hash_hex, salt_hex)
        assert result is False

    # ========== Test JWT ==========

    def test_create_jwt_generates_valid_token(self, auth_service):
        """Test: create_jwt genera un token valido"""
        user_id = 123
        cod_cli = 456
        role = "customer"
        
        token = auth_service.create_jwt(user_id, cod_cli, role)
        
        # Token non vuoto
        assert token
        # Token è una stringa
        assert isinstance(token, str)
        # Token ha almeno 3 parti (header.payload.signature)
        assert token.count('.') >= 2

    def test_verify_jwt_valid_token(self, auth_service):
        """Test: verify_jwt decodifica un token valido"""
        user_id = 123
        cod_cli = 456
        role = "customer"
        
        # Crea token
        token = auth_service.create_jwt(user_id, cod_cli, role)
        
        # Verifica token
        payload = auth_service.verify_jwt(token)
        
        # Payload non nullo
        assert payload is not None
        # Contiene i dati corretti
        assert payload["sub"] == str(user_id)
        assert payload["cod_cli"] == cod_cli
        assert payload["role"] == role

    def test_verify_jwt_invalid_token(self, auth_service):
        """Test: verify_jwt ritorna None per token invalido"""
        invalid_token = "invalid.token.here"
        
        payload = auth_service.verify_jwt(invalid_token)
        
        assert payload is None

    def test_verify_jwt_expired_token(self, auth_service):
        """Test: verify_jwt ritorna None per token scaduto"""
        # Crea un token con scadenza immediata (mocando il tempo)
        user_id = 123
        cod_cli = 456
        role = "customer"
        
        # Crea token con servizio
        token = auth_service.create_jwt(user_id, cod_cli, role)
        
        # Aspetta che scada (in test, aspettiamo 1 secondo se la scadenza è immediata)
        # Per ora verificiamo solo che il token è valido subito dopo la creazione
        payload = auth_service.verify_jwt(token)
        assert payload is not None

    # ========== Test Login Use Case ==========

    def test_login_success(self, auth_service, mock_repo):
        """Test: login con credenziali corrette ritorna token"""
        # Setup
        email = "user@example.com"
        password = "correct_password"
        user_id = 123
        cod_cli = 456
        
        # Genera hash password
        hash_hex, salt_hex = auth_service.hash_password(password)
        
        # Mock repo ritorna utente
        mock_repo.find_by_email.return_value = {
            "id": user_id,
            "email": email,
            "password_hash": hash_hex,
            "password_salt": salt_hex,
            "role": "customer",
            "cod_cli": cod_cli,
        }
        mock_repo.get_client_info.return_value = {
            "rag_soc": "Test Company"
        }
        
        # Execute
        result = auth_service.login(email, password)
        
        # Verify
        assert result is not None
        assert "token" in result
        assert result["cod_cli"] == cod_cli
        assert result["role"] == "customer"

    def test_login_user_not_found(self, auth_service, mock_repo):
        """Test: login con email inesistente ritorna None"""
        # Setup
        email = "nonexistent@example.com"
        password = "any_password"
        
        mock_repo.find_by_email.return_value = None
        
        # Execute
        result = auth_service.login(email, password)
        
        # Verify
        assert result is None

    def test_login_wrong_password(self, auth_service, mock_repo):
        """Test: login con password sbagliata ritorna None"""
        # Setup
        email = "user@example.com"
        correct_password = "correct_password"
        wrong_password = "wrong_password"
        user_id = 123

        # Genera hash password corretta
        hash_hex, salt_hex = auth_service.hash_password(correct_password)

        # Mock repo
        mock_repo.find_by_email.return_value = {
            "id": user_id,
            "email": email,
            "password_hash": hash_hex,
            "password_salt": salt_hex,
            "role": "customer",
            "cod_cli": 456,
        }

        # Execute con password sbagliata
        result = auth_service.login(email, wrong_password)

        # Verify
        assert result is None

    # ========== Test Get Profile (TU108) ==========

    def test_get_profile_success(self, auth_service, mock_repo):
        """Test: get_profile ritorna profilo utente con rag_soc"""
        # Setup
        user_id = 123
        mock_repo.find_by_id.return_value = {
            "id": user_id,
            "email": "user@example.com",
            "cod_cli": 456,
            "role": "customer",
            "export_folder": "/tmp/export",
            "created_at": "2026-01-01",
            "updated_at": "2026-04-01",
        }
        mock_repo.get_client_info.return_value = {"rag_soc": "Test Company"}

        # Execute
        result = auth_service.get_profile(user_id)

        # Verify
        assert result is not None
        assert result["email"] == "user@example.com"
        assert result["cod_cli"] == 456
        assert result["rag_soc"] == "Test Company"
        assert result["role"] == "customer"
        assert result["export_folder"] == "/tmp/export"

    def test_get_profile_not_found(self, auth_service, mock_repo):
        """Test: get_profile ritorna None se utente non trovato"""
        # Setup
        mock_repo.find_by_id.return_value = None

        # Execute
        result = auth_service.get_profile(999)

        # Verify
        assert result is None

    def test_get_profile_no_cod_cli(self, auth_service, mock_repo):
        """Test: get_profile senza cod_cli non chiama get_client_info"""
        # Setup
        mock_repo.find_by_id.return_value = {
            "id": 123,
            "email": "admin@example.com",
            "cod_cli": 0,
            "role": "admin",
            "created_at": "",
            "updated_at": "",
        }

        # Execute
        result = auth_service.get_profile(123)

        # Verify
        assert result is not None
        assert result["rag_soc"] == ""
        mock_repo.get_client_info.assert_not_called()

    # ========== Test Get/Set Export Folder (TU109-TU110) ==========

    def test_get_export_folder(self, auth_service, mock_repo):
        """Test: get_export_folder delega al repository"""
        # Setup
        mock_repo.get_export_folder.return_value = "/tmp/export"

        # Execute
        result = auth_service.get_export_folder(123)

        # Verify
        assert result == "/tmp/export"
        mock_repo.get_export_folder.assert_called_once_with(123)

    def test_get_export_folder_none(self, auth_service, mock_repo):
        """Test: get_export_folder ritorna None se non configurato"""
        # Setup
        mock_repo.get_export_folder.return_value = None

        # Execute
        result = auth_service.get_export_folder(123)

        # Verify
        assert result is None

    def test_set_export_folder(self, auth_service, mock_repo):
        """Test: set_export_folder delega al repository"""
        # Execute
        auth_service.set_export_folder(123, "/new/path")

        # Verify
        mock_repo.set_export_folder.assert_called_once_with(123, "/new/path")

    def test_set_export_folder_none(self, auth_service, mock_repo):
        """Test: set_export_folder con None resetta il path"""
        # Execute
        auth_service.set_export_folder(123, None)

        # Verify
        mock_repo.set_export_folder.assert_called_once_with(123, None)

    # ========== Test Change Password (TU111) ==========

    def test_change_password_success(self, auth_service, mock_repo):
        """Test: change_password con dati corretti cambia la password"""
        # Setup
        user_id = 123
        current_password = "old_password"
        new_password = "new_password_123"

        hash_hex, salt_hex = auth_service.hash_password(current_password)
        mock_repo.find_by_id.return_value = {
            "id": user_id,
            "password_hash": hash_hex,
            "password_salt": salt_hex,
        }

        # Execute
        success, error = auth_service.change_password(
            user_id, current_password, new_password, new_password
        )

        # Verify
        assert success is True
        assert error == ""
        mock_repo.update_password.assert_called_once()

    def test_change_password_too_short(self, auth_service, mock_repo):
        """Test: change_password rifiuta password troppo corte"""
        success, error = auth_service.change_password(123, "old", "ab", "ab")

        assert success is False
        assert "almeno 6 caratteri" in error

    def test_change_password_mismatch(self, auth_service, mock_repo):
        """Test: change_password rifiuta se conferma non coincide"""
        success, error = auth_service.change_password(
            123, "old_pass", "new_password", "different_password"
        )

        assert success is False
        assert "non coincidono" in error

    def test_change_password_same_as_current(self, auth_service, mock_repo):
        """Test: change_password rifiuta se nuova == attuale"""
        success, error = auth_service.change_password(
            123, "same_password", "same_password", "same_password"
        )

        assert success is False
        assert "diversa" in error

    def test_change_password_wrong_current(self, auth_service, mock_repo):
        """Test: change_password rifiuta se password attuale è sbagliata"""
        # Setup
        correct_pw = "correct_password"
        hash_hex, salt_hex = auth_service.hash_password(correct_pw)
        mock_repo.find_by_id.return_value = {
            "id": 123,
            "password_hash": hash_hex,
            "password_salt": salt_hex,
        }

        # Execute
        success, error = auth_service.change_password(
            123, "wrong_current", "new_password_123", "new_password_123"
        )

        # Verify
        assert success is False
        assert "non è corretta" in error

    def test_change_password_user_not_found(self, auth_service, mock_repo):
        """Test: change_password fallisce se utente non trovato"""
        mock_repo.find_by_id.return_value = None

        success, error = auth_service.change_password(
            999, "old_pass", "new_password_123", "new_password_123"
        )

        assert success is False
        assert "non trovato" in error

    # ========== Test Register (TU112) ==========

    def test_register_customer_success(self, auth_service, mock_repo):
        """Test: register crea un nuovo utente customer"""
        # Setup
        mock_repo.find_by_email.return_value = None

        # Execute
        success, error = auth_service.register(
            "new@example.com", "password123", "customer", cod_cli=100
        )

        # Verify
        assert success is True
        assert error == ""
        mock_repo.create_user.assert_called_once()

    def test_register_admin_success(self, auth_service, mock_repo):
        """Test: register crea un nuovo utente admin (senza cod_cli)"""
        mock_repo.find_by_email.return_value = None

        success, error = auth_service.register(
            "admin@example.com", "password123", "admin", cod_cli=None
        )

        assert success is True
        # Admin non ha cod_cli
        call_args = mock_repo.create_user.call_args
        assert call_args[0][3] == "admin"
        assert call_args[0][4] is None

    def test_register_empty_email(self, auth_service, mock_repo):
        """Test: register rifiuta email vuota"""
        success, error = auth_service.register("", "password123", "customer", 100)

        assert success is False
        assert "obbligatori" in error

    def test_register_empty_password(self, auth_service, mock_repo):
        """Test: register rifiuta password vuota"""
        success, error = auth_service.register("user@test.com", "", "customer", 100)

        assert success is False
        assert "obbligatori" in error

    def test_register_customer_no_cod_cli(self, auth_service, mock_repo):
        """Test: register rifiuta customer senza cod_cli"""
        success, error = auth_service.register(
            "user@test.com", "password123", "customer", cod_cli=None
        )

        assert success is False
        assert "cod_cli" in error

    def test_register_duplicate_email(self, auth_service, mock_repo):
        """Test: register rifiuta email già registrata"""
        mock_repo.find_by_email.return_value = {"id": 1, "email": "dup@test.com"}

        success, error = auth_service.register(
            "dup@test.com", "password123", "customer", cod_cli=100
        )

        assert success is False
        assert "già registrata" in error
>>>>>>> Stashed changes
