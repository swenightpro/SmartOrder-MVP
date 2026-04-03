import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from adapters.database import close_pool
from adapters.postgres_adapter import PostgresAdapter
from adapters.openai_adapter import OpenAIAdapter
from services.auth_service import AuthService
from services.conversation_service import ConversationService
from services.cart_service import CartService
from services.order_service import OrderService
from services.product_service import ProductService
from services.feedback_service import FeedbackService
from services.client_service import ClientService
from services.ticket_service import TicketService
from services.sse_broadcaster import get_broadcaster

from controllers import (
    auth_controller,
    conversation_controller,
    cart_controller,
    order_controller,
    product_controller,
    feedback_controller,
    health_controller,
    client_controller,
    ticket_controller,
    sse_controller,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Singleton delle implementazioni concrete
_db = PostgresAdapter()
_ai_client = OpenAIAdapter()
_auth_service = AuthService(_db)
_broadcaster = get_broadcaster()
_conversation_service = ConversationService(_db, _ai_client, _broadcaster)
_cart_service = CartService(_db, _broadcaster)
_order_service = OrderService(_db, _db, _broadcaster)
_product_service = ProductService(_db)
_feedback_service = FeedbackService(_db)
_client_service = ClientService(_db)
_ticket_service = TicketService(_db, _db, _broadcaster)

# Pre-cache auth service per _get_current_user (evita di ricreare istanze su ogni richiesta)
auth_controller._auth_svc = _auth_service
ticket_controller._ticket_svc = _ticket_service
sse_controller._sse_auth_svc = _auth_service

def _provide_auth_service() -> AuthService:
    return _auth_service

def _provide_conversation_service() -> ConversationService:
    return _conversation_service

def _provide_cart_service() -> CartService:
    return _cart_service

def _provide_order_service() -> OrderService:
    return _order_service

def _provide_product_service() -> ProductService:
    return _product_service

def _provide_feedback_service() -> FeedbackService:
    return _feedback_service

def _provide_client_service() -> ClientService:
    return _client_service

def _provide_ticket_service() -> TicketService:
    return _ticket_service

def _provide_db() -> PostgresAdapter:
    return _db

def _configure_dependency_overrides(app: FastAPI) -> None:
    """Collega le dipendenze astratte dei controller alle implementazioni concrete."""
    app.dependency_overrides[auth_controller._get_auth_service] = _provide_auth_service
    app.dependency_overrides[conversation_controller._get_conversation_service] = _provide_conversation_service
    app.dependency_overrides[cart_controller._get_cart_service] = _provide_cart_service
    app.dependency_overrides[cart_controller._get_db_adapter] = _provide_db
    app.dependency_overrides[order_controller._get_order_service] = _provide_order_service
    app.dependency_overrides[product_controller._get_product_service] = _provide_product_service
    app.dependency_overrides[feedback_controller._get_feedback_service] = _provide_feedback_service
    app.dependency_overrides[client_controller._get_client_service] = _provide_client_service
    app.dependency_overrides[ticket_controller._get_ticket_service] = _provide_ticket_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Backend SmartOrder avviato")
    yield
    close_pool()
    logger.info("🛑 Backend SmartOrder terminato")

settings = get_settings()

app = FastAPI(
    title="SmartOrder Backend",
    description="Backend unificato per SmartOrder — architettura Ports & Adapters",
    version="1.0.0",
    lifespan=lifespan,
)

_configure_dependency_overrides(app)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled backend exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Errore interno backend"},
    )

# Permette al frontend (localhost:3000 in dev) di chiamare il backend (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,  # Necessario per i cookie HTTPOnly cross-origin
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_controller.router)
app.include_router(auth_controller.router)
app.include_router(conversation_controller.router)
app.include_router(cart_controller.router)
app.include_router(order_controller.router)
app.include_router(product_controller.router)
app.include_router(feedback_controller.router)
app.include_router(client_controller.router)
app.include_router(ticket_controller.router)
app.include_router(sse_controller.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )