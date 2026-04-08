#!/usr/bin/env python3
"""Debug script: testa il flusso di image lookup step by step."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from openai import OpenAI
from config import get_settings
from adapters.postgres_adapter import PostgresAdapter
from adapters.database import get_pool

s = get_settings()
db = PostgresAdapter(get_pool())
ai = OpenAI(api_key=s.openai_api_key)

# === STEP 1: verifica embeddings nel DB ===
print("=== STEP 1: Embeddings ===")
has_emb = db.has_embeddings()
print(f"  Embeddings presenti: {has_emb}")
if has_emb:
    count = db.execute_query_one("SELECT COUNT(*) as cnt FROM product_embeddings")
    print(f"  Totale embeddings: {count['cnt']}")

# === STEP 2: test lookup testuale ===
print("\n=== STEP 2: ILIKE testuale (find_product_by_name) ===")
# Prova con un nome plausibile che potrebbe essere in una lista della spesa
test_names = ["Coca Cola", "Acqua", "Birra", "Pane", "Latte"]
for name in test_names:
    found = db.find_product_by_name(name, cod_cli=1)
    if found:
        print(f"  '{name}' -> TROVATO: {found['des_art']} ({found['cod_art']})")
    else:
        print(f"  '{name}' -> NON TROVATO")

# === STEP 3: test vector search diretta ===
print("\n=== STEP 3: Vector search (search_products_vector) ===")
embedding = ai.embeddings.create(
    model=s.embedding_model,
    input="Coca Cola",
).data[0].embedding
results = db.search_products_vector(embedding, cod_cli=1, limit=5)
for r in results:
    print(f"  {r['des_art']} (similarity: {r['similarity']:.3f})")

# === STEP 4: test merged lookup ===
print("\n=== STEP 4: Merged lookup (find_product_by_name_merged) ===")
for name in test_names:
    emb = ai.embeddings.create(model=s.embedding_model, input=name).data[0].embedding
    found = db.find_product_by_name_merged(name, cod_cli=1, embedding=emb)
    if found:
        ts = found.get('text_score', 0)
        vs = found.get('vector_score', 0)
        ms = found.get('merged_score', 0)
        print(f"  '{name}' -> {found['des_art']} | text={ts:.2f} vec={vs:.2f} merged={ms:.2f}")
    else:
        print(f"  '{name}' -> NON TROVATO")

# === STEP 5: verifica cod_cli 1 ha prodotti ===
print("\n=== STEP 5: Prodotti in assortimento per cod_cli=1 ===")
rows = db.execute_query(
    "SELECT COUNT(*) as cnt FROM asscli WHERE cod_cli = %s",
    (1,)
)
print(f"  Prodotti in asscli per cod_cli=1: {rows[0]['cnt']}")
