# ===========================================================================
# controllers/register_controller.py — Controller registrazione (Layer 1)
#
# Endpoint: POST /auth/register
# Tenuto separato dal controller auth principale (sarà rimosso in futuro).
# ===========================================================================

from fastapi import APIRouter, Depends, HTTPException
from domain.schemas import RegisterRequest
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["register"])


def _get_auth_service() -> AuthService:
    """Factory per DI — iniettata in main.py."""
    raise NotImplementedError("Override in main.py")


@router.post("/register")
def register(body: RegisterRequest,
             auth_service: AuthService = Depends(_get_auth_service)):
    ok, error_msg = auth_service.register(
        body.email, body.password, body.role, body.cod_cli
    )
    if not ok:
        raise HTTPException(status_code=400, detail=error_msg)
    return {"success": True, "message": "Utente creato con successo"}
