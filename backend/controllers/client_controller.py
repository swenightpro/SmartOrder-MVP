from fastapi import APIRouter, Depends
from services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


def _get_client_service() -> ClientService:
    """Factory per DI — iniettata in main.py."""
    raise NotImplementedError("Override in main.py")


@router.get("/search")
def search_clients(q: str = "",
                   client_service: ClientService = Depends(_get_client_service)):
    query = q.strip()
    if not query:
        return []
    return client_service.search_clients(query)
