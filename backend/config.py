from __future__ import annotations
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
from dataclasses import dataclass, field


_ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    """Configurazione dell'applicazione."""

    # --- Database (PostgreSQL) ---
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

    # --- Cookie ---
    cookie_secure: bool = False       # True in produzione (HTTPS)
    cookie_samesite: str = "lax"      # "none" in produzione (cross-domain)

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"  # comma-separated in prod
    cors_origin_regex: str = r"^https?://((localhost|127\.0\.0\.1)(:\d+)?|.*\.up\.railway\.app)$"

    # --- AI models ---
    ai_model: str = "gpt-5.4-2026-03-05"
    ai_model_mini: str = "gpt-5.4-2026-03-05"
    whisper_model: str = "whisper-1"
    embedding_model: str = "text-embedding-3-small"

    # --- Confidence Scoring ---
    # Pesi per il calcolo del confidence score (devono sommare a 1.0)
    signal_weights: dict = field(default_factory=lambda: {
        # Peso minimo: fallback storico=0.5 non deve abbassare troppo i nuovi articoli.
        "history_match": 0.04,
        # Peso contenuto: con embeddings mancanti il fallback a 0.3 non deve penalizzare troppo.
        "similarity": 0.06,
        # Segnale forte: quando il match testuale è buono deve trainare lo score.
        "match_type": 0.35,
        # Intent utile ma secondario rispetto a match e quantità.
        "intent_type": 0.10,
        # Segnale principale: quantità esplicita alza la confidenza nei casi operativi reali.
        "quantity_explicit": 0.45,
    })
    # Soglia UX: confidence sotto questo valore mostra warning all'utente
    low_confidence_threshold: float = 0.70
    # Soglia gap per auto-add: top_1 - top_2 >= gap_confidence_threshold → auto-add
    gap_confidence_threshold: float = 0.15

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()