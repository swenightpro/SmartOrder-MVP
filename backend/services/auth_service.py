import hashlib
import os
import time
import jwt as pyjwt  # PyJWT
from typing import Optional

from config import get_settings
from ports.i_user_repository import IUserRepository


class AuthService:
    """Servizio applicativo di autenticazione."""

    def __init__(self, user_repo: IUserRepository):
        self._repo = user_repo
        self._settings = get_settings()

    # =======================================================================
    # Password hashing (scrypt — compatibile con il PoC Node.js)
    # =======================================================================

    def _derive_scrypt_hash(
        self,
        password: str,
        salt: bytes,
        n: int,
        r: int,
        p: int,
        dklen: int,
        pepper: str,
    ) -> str:
        secret = f"{password}{pepper}".encode("utf-8")
        key = hashlib.scrypt(
            secret,
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=dklen,
        )
        return key.hex()

    def _password_profiles(self) -> list[tuple[int, int, int, int]]:
        primary = (
            self._settings.password_hash_n,
            self._settings.password_hash_r,
            self._settings.password_hash_p,
            self._settings.password_hash_dklen,
        )
        profiles = [primary]

        legacy = (
            self._settings.password_legacy_n,
            self._settings.password_legacy_r,
            self._settings.password_legacy_p,
            self._settings.password_legacy_dklen,
        )
        if all(v > 0 for v in legacy) and legacy != primary:
            profiles.append(legacy)

        return profiles

    def hash_password(self, password: str) -> tuple[str, str]:
        """Genera hash e salt per una password.

        Returns:
            Tupla (password_hash_hex, salt_hex).
        """
        salt = os.urandom(16)
        key_hex = self._derive_scrypt_hash(
            password=password,
            salt=salt,
            n=self._settings.password_hash_n,
            r=self._settings.password_hash_r,
            p=self._settings.password_hash_p,
            dklen=self._settings.password_hash_dklen,
            pepper=self._settings.password_pepper,
        )
        return key_hex, salt.hex()

    def verify_password(self, password: str, stored_hash: str, stored_salt: str) -> bool:
        """Verifica una password contro hash e salt salvati."""
        try:
            salt = bytes.fromhex(stored_salt)
            expected_hash = (stored_hash or "").lower()

            peppers = [self._settings.password_pepper]
            if self._settings.password_pepper:
                peppers.append("")

            for n, r, p, dklen in self._password_profiles():
                for pepper in peppers:
                    candidate = self._derive_scrypt_hash(
                        password=password,
                        salt=salt,
                        n=n,
                        r=r,
                        p=p,
                        dklen=dklen,
                        pepper=pepper,
                    )
                    if candidate == expected_hash:
                        return True

            return False
        except Exception:
            return False

    # =======================================================================
    # JWT
    # =======================================================================

    def create_jwt(self, user_id: int, cod_cli: int, role: str) -> str:
        """Crea un token JWT."""
        now = time.time()
        payload = {
            "sub": str(user_id),
            "cod_cli": cod_cli,
            "role": role,
            "iat": int(now),
            "exp": int(now + self._settings.jwt_expiration_hours * 3600),
        }
        return pyjwt.encode(payload, self._settings.jwt_secret,
                            algorithm=self._settings.jwt_algorithm)

    def verify_jwt(self, token: str) -> Optional[dict]:
        """Verifica e decodifica un JWT. Ritorna il payload o None."""
        try:
            payload = pyjwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
            )
            return payload
        except pyjwt.ExpiredSignatureError:
            return None
        except pyjwt.InvalidTokenError:
            return None

    # =======================================================================
    # Use cases
    # =======================================================================

    def login(self, email: str, password: str) -> Optional[dict]:
        """Autentica utente. Ritorna {token, cod_cli, rag_soc, role} o None."""
        user = self._repo.find_by_email(email)
        if not user:
            return None

        if not self.verify_password(password, user["password_hash"], user["password_salt"]):
            return None

        cod_cli = int(user.get("cod_cli") or 0)
        rag_soc = ""
        if cod_cli:
            client = self._repo.get_client_info(cod_cli)
            rag_soc = client["rag_soc"] if client else ""

        token = self.create_jwt(user["id"], cod_cli, user["role"])
        return {
            "token": token,
            "cod_cli": cod_cli,
            "rag_soc": rag_soc,
            "role": user["role"],
        }

    def get_profile(self, user_id: int) -> Optional[dict]:
        """Recupera profilo utente."""
        user = self._repo.find_by_id(user_id)
        if not user:
            return None

        cod_cli = int(user.get("cod_cli") or 0)
        rag_soc = ""
        if cod_cli:
            client = self._repo.get_client_info(cod_cli)
            rag_soc = client["rag_soc"] if client else ""

        return {
            "email": user["email"],
            "cod_cli": cod_cli,
            "rag_soc": rag_soc,
            "role": user["role"],
            "export_folder": user.get("export_folder"),
            "created_at": str(user.get("created_at", "")),
            "updated_at": str(user.get("updated_at", "")),
        }

    def get_export_folder(self, user_id: int) -> Optional[str]:
        return self._repo.get_export_folder(user_id)

    def set_export_folder(self, user_id: int, path: Optional[str]) -> None:
        self._repo.set_export_folder(user_id, path)

    def change_password(self, user_id: int, current_password: str,
                        new_password: str, confirm_new_password: str) -> tuple[bool, str]:
        """Cambio password. Ritorna (successo, messaggio_errore)."""
        if len(new_password) < 6:
            return False, "La nuova password deve avere almeno 6 caratteri"

        if new_password != confirm_new_password:
            return False, "Le nuove password non coincidono"

        if current_password == new_password:
            return False, "La nuova password deve essere diversa da quella attuale"

        user = self._repo.find_by_id(user_id)
        if not user:
            return False, "Utente non trovato"

        if not self.verify_password(current_password, user["password_hash"], user["password_salt"]):
            return False, "La password attuale non è corretta"

        new_hash, new_salt = self.hash_password(new_password)
        self._repo.update_password(user_id, new_hash, new_salt)
        return True, ""

    def register(self, email: str, password: str, role: str,
                 cod_cli: Optional[int]) -> tuple[bool, str]:
        """Registra un nuovo utente. Ritorna (successo, messaggio_errore)."""
        if not email or not password:
            return False, "Email e password sono obbligatori"

        # Validazione ruolo
        user_role = "admin" if role == "admin" else "customer"

        if user_role == "customer" and not cod_cli:
            return False, "Codice cliente (cod_cli) obbligatorio per i customer"

        # Check duplicato
        existing = self._repo.find_by_email(email)
        if existing:
            return False, "Email già registrata. Usa un'altra email."

        pw_hash, pw_salt = self.hash_password(password)
        self._repo.create_user(email, pw_hash, pw_salt, user_role,
                               cod_cli if user_role == "customer" else None)
        return True, ""
