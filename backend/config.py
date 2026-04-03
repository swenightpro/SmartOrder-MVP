from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse


_ENV_FILE = Path(__file__).resolve().parent / ".env"

class Settings(BaseSettings):
    """Configurazione dell'applicazione."""

    database_url: str = ""
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = ""
    db_name: str = "smartorder"

    # --- OpenAI ---
    openai_api_key: str = ""

    # --- JWT / Auth ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 72  # 3 giorni
    cookie_name: str = "smartorder_session"

    # --- Password hashing (scrypt) ---
    password_pepper: str = ""
    password_hash_n: int = 16384
    password_hash_r: int = 8
    password_hash_p: int = 1
    password_hash_dklen: int = 64

    # Profilo legacy opzionale per compatibilita tra backend diversi.
    # Se lasciato a 0, viene ignorato.
    password_legacy_n: int = 0
    password_legacy_r: int = 0
    password_legacy_p: int = 0
    password_legacy_dklen: int = 0

    # --- Server ---
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    cookie_secure: bool = False

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"  # comma-separated in prod
    cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.up\.railway\.app$"

    # --- AI models ---
    ai_model: str = "gpt-4o"
    ai_model_mini: str = "gpt-4o-mini"
    whisper_model: str = "whisper-1"

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_config(self) -> dict:
        """Ritorna i parametri di connessione DB, parsando DATABASE_URL se presente."""
        if self.database_url:
            parsed = urlparse(self.database_url)
            return {
                "host": parsed.hostname or self.db_host,
                "port": parsed.port or self.db_port,
                "user": parsed.username or self.db_user,
                "password": parsed.password or self.db_password,
                "database": parsed.path.lstrip("/") or self.db_name,
            }
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "database": self.db_name,
        }

@lru_cache()
def get_settings() -> Settings:
    return Settings()