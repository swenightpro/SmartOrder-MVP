class ClientService:
    def __init__(self, client_repo):
        self._repo = client_repo

    def search_clients(self, query: str, limit: int = 10) -> list[dict]:
        return self._repo.search_clients(query, limit)
