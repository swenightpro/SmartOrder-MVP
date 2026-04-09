from fastapi import APIRouter, Request, Response, HTTPException, Depends, Body
from typing import Optional
from domain.schemas import LoginRequest, ChangePasswordRequest
from services.auth_service import AuthService
from config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

# Cached instances (overridden by main.py dependency_overrides)
_auth_svc: Optional[AuthService] = None


def _get_auth_service() -> AuthService:
    """Factory per DI — iniettata in main.py."""
    if _auth_svc:
        return _auth_svc
    raise NotImplementedError("Override in main.py")


def _get_current_user(request: Request) -> dict:
    """Middleware di autenticazione: estrae e valida il JWT dal cookie."""
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Non autenticato")

    auth = _get_auth_service()
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
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
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
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )
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
        user["userId"], body.current_password, body.new_password, body.confirm_new_password
    )
    if not ok:
        status = 401 if "attuale" in error_msg else 400
        raise HTTPException(status_code=status, detail=error_msg)
    return {"success": True}


@router.get("/export-folder")
def get_export_folder(user: dict = Depends(_get_current_user),
                     auth_service: AuthService = Depends(_get_auth_service)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo operatori")
    folder = auth_service.get_export_folder(user["userId"])
    return {"export_folder": folder}


@router.put("/export-folder")
def set_export_folder(body: dict = Body(default={}),
                      user: dict = Depends(_get_current_user),
                      auth_service: AuthService = Depends(_get_auth_service)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo operatori")
    path = body.get("export_folder")
    # Accetta stringa vuota o null per "non configurata"
    auth_service.set_export_folder(user["userId"], path if path else None)
    return {"success": True}


@router.get("/sse-token")
def sse_token(request: Request):
    """Restituisce il JWT dal cookie HTTPOnly per connessioni SSE dirette."""
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Non autenticato")
    return {"token": token}

