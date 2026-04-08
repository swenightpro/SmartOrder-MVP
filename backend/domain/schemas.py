from pydantic import BaseModel, Field
from typing import Optional


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "customer"
    cod_cli: Optional[int] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str


class UserResponse(BaseModel):
    email: str
    cod_cli: int = 0
    rag_soc: str = ""
    role: str = "customer"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Chat / Conversation
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    clientId: int
    history: list[dict] = Field(default_factory=list)
    session_id: Optional[int] = None
    pending_cart_edits: Optional[list] = None


class DisambiguationCandidate(BaseModel):
    cod_art: str
    name: str
    des_um: Optional[str] = None
    pezzi_conf: int = 1
    des_tipo_um: Optional[str] = None
    quantity: int = 1


class ChatResponse(BaseModel):
    success: bool = True
    response: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    user_message_id: Optional[int] = None
    ai_message_id: Optional[int] = None
    product_items: Optional[list[dict]] = None
    product_codes: Optional[list[str]] = None
    product_confidences: Optional[dict] = None
    order_confirmed: Optional[bool] = None
    cart_edits: Optional[list[dict]] = None
    edit_confirmed: Optional[bool] = None
    disambiguation_candidates: Optional[list[dict]] = None


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

class AddByNameRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=200)
    qta: int = Field(default=1, ge=1, le=9999)
    session_id: Optional[int] = None


class CartActionRequest(BaseModel):
    action: str  # "add", "remove", "update_quantity"
    cod_art: Optional[str] = None
    qta: Optional[int] = None
    id: Optional[int] = None
    source: Optional[str] = "customer"
    ai_confidence: Optional[float] = None
    related_message_id: Optional[int] = None
    session_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

class OrderItemRequest(BaseModel):
    cod_art: str
    qta: int
    source: str = "customer"
    last_updated_by: str = "customer"
    ai_confidence: Optional[float] = None
    related_message_id: Optional[int] = None


class CreateOrderRequest(BaseModel):
    cod_cli: Optional[int] = None
    session_id: Optional[int] = None
    items: list[OrderItemRequest]


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class SaveMessageRequest(BaseModel):
    session_id: int
    sender: str  # "user" | "ai" | "system"
    content: str = Field(default="", max_length=5000)


class FeedbackRequest(BaseModel):
    message_id: int
    is_positive: Optional[bool] = None
    reason_category: Optional[str] = None
    comment: Optional[str] = None
    action: Optional[str] = None  # "delete" per rimozione


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

class CreateTicketRequest(BaseModel):
    session_id: int


class TicketLockRequest(BaseModel):
    operator_id: Optional[int] = None


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class CloseTicketRequest(BaseModel):
    closed_by: str = Field(default="operator")  # "operator" o "customer"


class TicketResponse(BaseModel):
    ticket: dict


class TicketListResponse(BaseModel):
    tickets: list[dict]


class TicketAnalyticsResponse(BaseModel):
    overview: dict
