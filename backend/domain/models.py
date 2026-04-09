from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class User:
    """Oggetto di dominio utente — immutabile dopo la creazione."""
    id: int
    email: str
    cod_cli: int
    role: str
    password_hash: str
    password_salt: str
    is_active: bool = True
    export_folder: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class Session:
    """Oggetto di dominio sessione chat — immutabile dopo la creazione."""
    id: int
    user_id: int
    status: str
    created_at: Optional[str] = None


@dataclass(frozen=True)
class CartItem:
    """Oggetto di dominio articolo nel carrello — immutabile dopo la creazione."""
    id: int
    cod_art: str
    qta: int
    source: str = "customer"
    session_id: Optional[int] = None
    last_updated_by: Optional[str] = None
    ai_confidence: Optional[float] = None
    related_message_id: Optional[int] = None
    updated_at: Optional[str] = None
    # Campi arricchiti dal join con anaart
    des_art: Optional[str] = None
    des_um: Optional[str] = None
    pezzi_conf: Optional[int] = None
    des_tipo_um: Optional[str] = None
    linea: Optional[str] = None
    famiglia: Optional[str] = None
    stato: Optional[str] = None


@dataclass(frozen=True)
class Ticket:
    """Oggetto di dominio ticket di assistenza — immutabile dopo la creazione."""
    id: int
    session_id: int
    cod_cli: int
    status: str
    locked_by: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
