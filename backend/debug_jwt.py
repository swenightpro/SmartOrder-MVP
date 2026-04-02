import os, dotenv
from config import get_settings
from services.auth_service import AuthService
from adapters.postgres_adapter import PostgresAdapter

dotenv.load_dotenv(".env")
auth = AuthService(PostgresAdapter())
token = auth.create_jwt(1, 100, "customer")
print("TOKEN:", token)
payload = auth.verify_jwt(token)
print("PAYLOAD:", payload)
