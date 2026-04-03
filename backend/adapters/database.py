import psycopg2
from psycopg2 import pool, extras
from config import get_settings

_pool: pool.SimpleConnectionPool | None = None

def get_pool() -> pool.SimpleConnectionPool:
    """Ritorna il pool di connessioni, creandolo se necessario."""
    global _pool
    if _pool is None or _pool.closed:
        s = get_settings()
        db = s.db_config
        _pool = pool.SimpleConnectionPool(
            minconn=2,
            maxconn=10,
            host=db["host"],
            port=db["port"],
            user=db["user"],
            password=db["password"],
            database=db["database"],
        )
    return _pool

def execute_query(query: str, params: tuple | list | None = None,
                  fetch: bool = True) -> list[dict]:
    """Esegue una query e ritorna i risultati come lista di dizionari.

    Args:
        query: Query SQL con placeholder %s.
        params: Parametri per la query.
        fetch: Se True, ritorna i risultati. Se False (INSERT/UPDATE/DELETE senza RETURNING), ritorna [].
    """
    conn = get_pool().getconn()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch and cur.description:
                rows = cur.fetchall()
                conn.commit()
                return [dict(row) for row in rows]
            conn.commit()
            return []
    except Exception:
        conn.rollback()
        raise
    finally:
        # rollback() può chiudere la connessione — verificare prima di restituirla
        try:
            if not conn.closed:
                get_pool().putconn(conn)
        except Exception:
            pass

def execute_query_one(query: str, params: tuple | list | None = None) -> dict | None:
    """Esegue una query e ritorna il primo risultato o None."""
    results = execute_query(query, params, fetch=True)
    return results[0] if results else None

def close_pool():
    """Chiude il pool di connessioni."""
    global _pool
    if _pool and not _pool.closed:
        _pool.closeall()
        _pool = None
