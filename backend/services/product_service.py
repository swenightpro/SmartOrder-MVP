class ProductService:
    def __init__(self, product_repo):
        # type hint rimosso per semplicità, usa PostgresAdapter (implementa il repository indirettamente)
        self._repo = product_repo

    def search_products(self, query: str, cod_cli: int, limit: int = 20) -> list[dict]:
        return self._repo.search_products(query, cod_cli, limit)
