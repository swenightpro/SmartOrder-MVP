# ===========================================================================
# controllers/auth_controller.py — Controller autenticazione (Layer 1)
#
# Endpoint: POST /auth/login, POST /auth/logout, GET /auth/me,
#           POST /auth/change-password
# ===========================================================================

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from domain.schemas import LoginRequest, ChangePasswordRequest
from services.auth_service import AuthService
from config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_service() -> AuthService:
    """Factory per DI — iniettata in main.py."""
    raise NotImplementedError("Override in main.py")


def _get_current_user(request: Request) -> dict:
    """Middleware di autenticazione: estrae e valida il JWT dal cookie."""
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Non autenticato")

    from adapters.postgres_adapter import PostgresAdapter
    repo = PostgresAdapter()
    auth = AuthService(repo)
    payload = auth.verify_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token non valido o scaduto")

    return {
        "userId": int(payload["sub"]),
        "cod_cli": payload.get("cod_cli", 0),
        "role": payload.get("role", "customer"),
    }


@router.post("/login")
def login(body: LoginRequest, response: Response,
          auth_service: AuthService = Depends(_get_auth_service)):
    result = auth_service.login(body.email, body.password)
    if not result:
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    settings = get_settings()

    # Imposta il JWT in un cookie HTTPOnly sicuro
    response.set_cookie(
        key=settings.cookie_name,
        value=result["token"],
        httponly=True,
        samesite="lax",
        secure=False,  # True in produzione con HTTPS
        max_age=settings.jwt_expiration_hours * 3600,
        path="/",
    )

    return {
        "success": True,
        "user": {
            "cod_cli": result["cod_cli"],
            "rag_soc": result["rag_soc"],
            "role": result["role"],
        },
    }


@router.post("/logout")
def logout(response: Response):
    settings = get_settings()
    response.delete_cookie(key=settings.cookie_name, path="/")
    return {"success": True}


@router.get("/me")
def me(user: dict = Depends(_get_current_user),
       auth_service: AuthService = Depends(_get_auth_service)):
    profile = auth_service.get_profile(user["userId"])
    if not profile:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return {"user": profile}


@router.post("/change-password")
def change_password(body: ChangePasswordRequest,
                    user: dict = Depends(_get_current_user),
                    auth_service: AuthService = Depends(_get_auth_service)):
    ok, error_msg = auth_service.change_password(
        user["userId"], body.current_password, body.new_password
    )
    if not ok:
        status = 401 if "attuale" in error_msg else 400
        raise HTTPException(status_code=status, detail=error_msg)
    return {"success": True}
