from pydantic import BaseModel, Field
from typing import Optional

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

class UserResponse(BaseModel):
    email: str
    cod_cli: int = 0
    rag_soc: str = ""
    role: str = "customer"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    clientId: int
    history: list[dict] = Field(default_factory=list)
    session_id: Optional[int] = None
    pending_cart_edits: Optional[list] = None

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

class CartActionRequest(BaseModel):
    action: str  # "add", "remove", "update_quantity"
    cod_art: Optional[str] = None
    qta: Optional[int] = None
    id: Optional[int] = None
    source: Optional[str] = "customer"
    ai_confidence: Optional[float] = None
    related_message_id: Optional[int] = None
    session_id: Optional[int] = None

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

class FeedbackRequest(BaseModel):
    message_id: int
    is_positive: Optional[bool] = None
    reason_category: Optional[str] = None
    comment: Optional[str] = None
    action: Optional[str] = None  # "delete" per rimozione

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
