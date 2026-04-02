# ===========================================================================
# controllers/product_controller.py — Controller ricerca prodotti (Layer 1)
#
# Endpoint: GET /products/search
# ===========================================================================

from fastapi import APIRouter, Depends, HTTPException
from controllers.auth_controller import _get_current_user
from services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["products"])


def _get_product_service() -> ProductService:
    """Factory per DI — iniettata in main.py."""
    raise NotImplementedError("Override in main.py")


@router.get("/search")
def search_products(q: str = "",
                    user: dict = Depends(_get_current_user),
                    product_service: ProductService = Depends(_get_product_service)):
    query = q.strip()
    if not query or len(query) < 2:
        return []
    return product_service.search_products(query, user["cod_cli"])
