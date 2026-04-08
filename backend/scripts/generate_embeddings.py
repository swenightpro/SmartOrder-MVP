import sys
import os

# Ensure the backend module is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from openai import OpenAI
from adapters.database import get_pool, execute_query, execute_query_one


def get_products_without_embeddings(limit: int = 0) -> list[dict]:
    """Recupera i prodotti che non hanno ancora un embedding."""
    if limit > 0:
        return execute_query(
            """SELECT a.cod_art, a.des_art
               FROM anaart a
               WHERE NOT EXISTS (
                   SELECT 1 FROM product_embeddings pe WHERE pe.cod_art = a.cod_art
               )
               LIMIT %s""",
            (limit,),
        )
    return execute_query(
        """SELECT a.cod_art, a.des_art
           FROM anaart a
           WHERE NOT EXISTS (
               SELECT 1 FROM product_embeddings pe WHERE pe.cod_art = a.cod_art
           )"""
    )


def upsert_embedding(cod_art: str, embedding: list[float]) -> None:
    """Inserisce o aggiorna l'embedding di un prodotto."""
    execute_query(
        """INSERT INTO product_embeddings (cod_art, embedding)
           VALUES (%s, %s::vector)
           ON CONFLICT (cod_art) DO UPDATE SET embedding = EXCLUDED.embedding""",
        (cod_art, embedding),
        fetch=False,
    )


def generate_embeddings(openai_client: OpenAI, model: str, batch_size: int = 100) -> int:
    """Genera embeddings per tutti i prodotti in batch.

    Ritorna il numero di embeddings generati.
    """
    products = get_products_without_embeddings()
    total = len(products)

    if total == 0:
        print("Tutti i prodotti hanno già un embedding. Niente da fare.")
        return 0

    print(f"Trovati {total} prodotti senza embedding.")
    print(f"Generazione in corso (batch size: {batch_size})...")

    for i in range(0, total, batch_size):
        batch = products[i:i + batch_size]
        texts = [p["des_art"] for p in batch]

        # OpenAI supports batch embeddings in a single API call
        response = openai_client.embeddings.create(model=model, input=texts)

        for product, embedding_data in zip(batch, response.data):
            cod_art = product["cod_art"]
            embedding = embedding_data.embedding
            upsert_embedding(cod_art, embedding)

        done = min(i + batch_size, total)
        print(f"  [{done}/{total}] embeddings generati")

    return total


def create_index() -> None:
    """Crea l'indice IVFFlat dopo l'inserimento dei dati (più efficiente)."""
    print("Creazione indice IVFFlat...")
    try:
        execute_query(
            """CREATE INDEX IF NOT EXISTS idx_product_embeddings_cosine
               ON product_embeddings USING ivfflat (embedding vector_cosine_ops)
               WITH (lists = 100)""",
            fetch=False,
        )
        print("Indice creato (o già esistente).")
    except Exception as e:
        print(f"Nota: indice non creato (potrebbe già esistere o pgvector non è installato): {e}")


def main() -> None:
    # Load environment
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)

    from config import get_settings
    s = get_settings()

    if not s.openai_api_key:
        print("ERRORE: openai_api_key non configurata in .env")
        sys.exit(1)

    if not s.embedding_model:
        print("ERRORE: embedding_model non configurato")
        sys.exit(1)

    # Initialize OpenAI client
    client = OpenAI(api_key=s.openai_api_key)

    # Ensure pgvector extension exists
    print("Verifica estensione pgvector...")
    try:
        execute_query("""CREATE EXTENSION IF NOT EXISTS vector""", fetch=False)
        print("Estensione pgvector OK.")
    except Exception as e:
        print(f"ERRORE: impossibile creare estensione pgvector: {e}")
        print("Assicurati che pgvector sia installato nel database PostgreSQL.")
        print("Vedi: https://github.com/pgvector/pgvector")
        sys.exit(1)

    # Ensure product_embeddings table exists
    print("Verifica tabella product_embeddings...")
    try:
        execute_query(
            """CREATE TABLE IF NOT EXISTS product_embeddings (
                cod_art VARCHAR(20) PRIMARY KEY REFERENCES anaart(cod_art) ON DELETE CASCADE,
                embedding vector(1536) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            fetch=False,
        )
        print("Tabella product_embeddings OK.")
    except Exception as e:
        print(f"ERRORE: impossibile creare tabella: {e}")
        sys.exit(1)

    # Generate embeddings
    count = generate_embeddings(client, s.embedding_model, batch_size=100)

    if count > 0:
        create_index()

    print(f"\nFatto! {count} embeddings generati.")
    print("Ora la ricerca vettoriale è attiva nel ConversationService.")


if __name__ == "__main__":
    main()
