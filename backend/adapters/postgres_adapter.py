# ===========================================================================
# adapters/postgres_adapter.py — Infrastructure Adapter per PostgreSQL
#
# Implementa IUserRepository, ISessionManager e IOrderRepository.
# Tutte le query SQL del sistema sono centralizzate qui.
# ===========================================================================

from typing import Optional
import json
from psycopg2 import errors as pg_errors

from ports.i_user_repository import IUserRepository
from ports.i_session_manager import ISessionManager
from ports.i_order_repository import IOrderRepository
from adapters.database import execute_query, execute_query_one


# ---------------------------------------------------------------------------
# Status di prodotto bloccanti (l'articolo non può essere ordinato)
# ---------------------------------------------------------------------------
BLOCKING_STATUSES = [
    "ARTICOLO SOSPESO",
    "SU AUTORIZZAZIONE",
    "DISPONIBILE DAL",
    "NON DISPONIBILE",
]


class PostgresAdapter(IUserRepository, ISessionManager, IOrderRepository):
    """Implementazione concreta di tutte le porte repository via PostgreSQL."""

    def _resync_id_sequence(self, table_name: str) -> None:
        """Riallinea la sequence di una tabella serial/identity al MAX(id)+1."""
        if table_name not in {"orders", "order_items"}:
            raise ValueError(f"Tabella non supportata per resync sequence: {table_name}")

        seq_row = execute_query_one(
            """SELECT REGEXP_REPLACE(
                       column_default,
                       '^nextval\\(''([^'']+)''::regclass\\)$',
                       '\\1'
                   ) AS seq_name
               FROM information_schema.columns
               WHERE table_schema = 'public'
                 AND table_name = %s
                 AND column_name = 'id'
               LIMIT 1""",
            (table_name,),
        )
        seq_name = (seq_row or {}).get("seq_name")
        if not seq_name:
            raise ValueError(f"Sequence non trovata per tabella {table_name}.id")

        if table_name == "orders":
            execute_query(
                """SELECT setval(
                       %s::regclass,
                       COALESCE((SELECT MAX(id) FROM orders), 0) + 1,
                       false
                   )""",
                (seq_name,),
                fetch=False,
            )
            return

        execute_query(
            """SELECT setval(
                   %s::regclass,
                   COALESCE((SELECT MAX(id) FROM order_items), 0) + 1,
                   false
               )""",
            (seq_name,),
            fetch=False,
        )

    # =======================================================================
    # IUserRepository
    # =======================================================================

    def find_by_email(self, email: str) -> Optional[dict]:
        return execute_query_one(
            """SELECT id, email, password_hash, password_salt, role, cod_cli,
                      is_active, created_at, updated_at
               FROM app_users
               WHERE LOWER(BTRIM(email)) = LOWER(BTRIM(%s))
               LIMIT 1""",
            (email,),
        )

    def find_by_id(self, user_id: int) -> Optional[dict]:
        return execute_query_one(
            """SELECT id, email, password_hash, password_salt, role, cod_cli,
                      is_active, created_at, updated_at
               FROM app_users WHERE id = %s LIMIT 1""",
            (user_id,),
        )

    def create_user(self, email: str, password_hash: str, password_salt: str,
                    role: str, cod_cli: Optional[int]) -> dict:
        row = execute_query_one(
            """INSERT INTO app_users (email, password_hash, password_salt, role, cod_cli, is_active)
               VALUES (%s, %s, %s, %s, %s, true)
               RETURNING id, email, role, cod_cli""",
            (email, password_hash, password_salt, role, cod_cli),
        )
        return row  # type: ignore

    def update_password(self, user_id: int, password_hash: str, password_salt: str) -> None:
        execute_query(
            "UPDATE app_users SET password_hash = %s, password_salt = %s, updated_at = NOW() WHERE id = %s",
            (password_hash, password_salt, user_id),
            fetch=False,
        )

    def get_client_info(self, cod_cli: int) -> Optional[dict]:
        return execute_query_one(
            "SELECT cod_cli, rag_soc FROM anacli WHERE cod_cli = %s LIMIT 1",
            (cod_cli,),
        )

    def search_clients(self, query: str, limit: int = 10) -> list[dict]:
        return execute_query(
            """SELECT cod_cli, rag_soc
               FROM anacli
               WHERE rag_soc ILIKE %s OR CAST(cod_cli AS TEXT) = %s
               LIMIT %s""",
            (f"%{query}%", query, limit),
        )

    # =======================================================================
    # ISessionManager — Sessioni
    # =======================================================================

    def get_active_session(self, user_id: int) -> Optional[dict]:
        return execute_query_one(
            """SELECT id, user_id, status, created_at
               FROM chat_sessions
               WHERE user_id = %s AND status = 'active'
               ORDER BY created_at DESC LIMIT 1""",
            (user_id,),
        )

    def create_session(self, user_id: int) -> dict:
        # Chiudi sessioni precedenti
        execute_query(
            "UPDATE chat_sessions SET status = 'completed', closed_at = NOW() WHERE user_id = %s AND status = 'active'",
            (user_id,),
            fetch=False,
        )
        row = execute_query_one(
            """INSERT INTO chat_sessions (user_id, status)
               VALUES (%s, 'active')
               RETURNING id, user_id, status, created_at""",
            (user_id,),
        )
        return row  # type: ignore

    # =======================================================================
    # ISessionManager — Messaggi
    # =======================================================================

    def get_messages(self, session_id: int) -> list[dict]:
        return execute_query(
            """SELECT id, session_id, sender, content, metadata, created_at
               FROM chat_messages
               WHERE session_id = %s
               ORDER BY created_at ASC""",
            (session_id,),
        )

    def save_message(self, session_id: int, sender: str, content: str,
                     metadata: Optional[str] = None) -> int:
        row = execute_query_one(
            """INSERT INTO chat_messages (session_id, sender, content, metadata)
               VALUES (%s, %s, %s, %s)
               RETURNING id""",
            (session_id, sender, content, metadata),
        )
        return row["id"]  # type: ignore

    # =======================================================================
    # ISessionManager — Carrello
    # =======================================================================

    def get_cart(self, user_id: int) -> list[dict]:
        session = self.get_active_session(user_id)
        if not session:
            return []
        
        return execute_query(
            """SELECT ci.id, ci.cod_art, ci.qta, ci.source, ci.last_updated_by,
                      ci.ai_confidence, ci.related_message_id, ci.updated_at,
                      a.des_art, a.des_um, a.pezzi_conf, a.des_tipo_um,
                      a.linea, a.famiglia, a.stato
               FROM cart_items ci
               LEFT JOIN anaart a ON ci.cod_art = a.cod_art
               WHERE ci.session_id = %s
               ORDER BY ci.updated_at ASC""",
            (session["id"],),
        )

    def add_to_cart(self, user_id: int, cod_art: str, qta: int,
                    source: str = "customer",
                    ai_confidence: Optional[float] = None,
                    related_message_id: Optional[int] = None) -> dict:
        session = self.get_active_session(user_id)
        if not session:
            # Crea sessione se non esiste
            session = self.create_session(user_id)

        # Evita errori SQL opachi in caso di cod_art non valido.
        product_exists = execute_query_one(
            "SELECT cod_art FROM anaart WHERE cod_art = %s LIMIT 1",
            (cod_art,),
        )
        if not product_exists:
            raise ValueError(f"Articolo non valido: {cod_art}")
            
        session_id = session["id"]

        # Upsert: se l'articolo esiste già, somma la quantità
        existing = execute_query_one(
            "SELECT id, qta FROM cart_items WHERE session_id = %s AND cod_art = %s",
            (session_id, cod_art),
        )
        if existing:
            new_qta = existing["qta"] + qta
            execute_query(
                """UPDATE cart_items
                   SET qta = %s, source = %s, last_updated_by = %s,
                       ai_confidence = %s, related_message_id = %s
                   WHERE id = %s""",
                (new_qta, source, source, ai_confidence, related_message_id, existing["id"]),
                fetch=False,
            )
            return {"id": existing["id"], "cod_art": cod_art, "qta": new_qta}
        else:
            row = execute_query_one(
                """INSERT INTO cart_items (session_id, cod_art, qta, source, last_updated_by,
                                          ai_confidence, related_message_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING id, cod_art, qta""",
                (session_id, cod_art, qta, source, source, ai_confidence, related_message_id),
            )
            return row  # type: ignore

    def remove_from_cart(self, cart_item_id: int, user_id: int) -> bool:
        session = self.get_active_session(user_id)
        if not session: return False
        result = execute_query(
            "DELETE FROM cart_items WHERE id = %s AND session_id = %s RETURNING id",
            (cart_item_id, session["id"]),
        )
        return len(result) > 0

    def update_cart_quantity(self, cart_item_id: int, user_id: int,
                            qta: int, source: str = "customer") -> bool:
        session = self.get_active_session(user_id)
        if not session: return False
        result = execute_query(
            """UPDATE cart_items SET qta = %s, source = %s, last_updated_by = %s
               WHERE id = %s AND session_id = %s RETURNING id""",
            (qta, source, source, cart_item_id, session["id"]),
        )
        return len(result) > 0

    def clear_cart(self, user_id: int) -> None:
        session = self.get_active_session(user_id)
        if not session: return
        execute_query(
            "DELETE FROM cart_items WHERE session_id = %s",
            (session["id"],),
            fetch=False,
        )

    # =======================================================================
    # IOrderRepository
    # =======================================================================

    def create_order(self, cod_cli: int, user_id: int,
                     session_id: Optional[int],
                     items: list[dict]) -> int:
        if not self.get_client_info(cod_cli):
            raise ValueError(f"Cliente non valido: {cod_cli}")

        allowed_actors = {"customer", "ai", "operator"}
        normalized_items: list[dict] = []
        for item in items:
            cod_art = str(item.get("cod_art") or "").strip()
            if not cod_art:
                raise ValueError("Articolo senza cod_art")

            product = execute_query_one(
                "SELECT cod_art FROM anaart WHERE cod_art = %s LIMIT 1",
                (cod_art,),
            )
            if not product:
                raise ValueError(f"Articolo {cod_art} non valido")

            qta = item.get("qta")
            if qta is None or float(qta) <= 0:
                raise ValueError(f"Quantita non valida per articolo {cod_art}")

            source = str(item.get("source") or "customer")
            last_updated_by = str(item.get("last_updated_by") or "customer")
            if source not in allowed_actors:
                raise ValueError(f"Source non valido per articolo {cod_art}: {source}")
            if last_updated_by not in allowed_actors:
                raise ValueError(f"last_updated_by non valido per articolo {cod_art}: {last_updated_by}")

            normalized_items.append({
                "cod_art": cod_art,
                "qta": float(qta),
                "source": source,
                "last_updated_by": last_updated_by,
                "ai_confidence": item.get("ai_confidence"),
                "related_message_id": item.get("related_message_id"),
            })

        # Inserisci header ordine
        try:
            order_row = execute_query_one(
                """INSERT INTO orders (cod_cli, user_id, session_id, data_ord)
                   VALUES (%s, %s, %s, NOW())
                   RETURNING id""",
                (cod_cli, user_id, session_id),
            )
        except pg_errors.UniqueViolation as exc:
            constraint_name = getattr(getattr(exc, "diag", None), "constraint_name", None)
            if constraint_name != "orders_pkey":
                raise

            self._resync_id_sequence("orders")
            order_row = execute_query_one(
                """INSERT INTO orders (cod_cli, user_id, session_id, data_ord)
                   VALUES (%s, %s, %s, NOW())
                   RETURNING id""",
                (cod_cli, user_id, session_id),
            )
        order_id = order_row["id"]  # type: ignore

        # Inserisci righe ordine
        for item in normalized_items:
            params = (
                order_id,
                item["cod_art"],
                item["qta"],
                item.get("source", "customer"),
                item.get("last_updated_by", "customer"),
                item.get("ai_confidence"),
                item.get("related_message_id"),
            )
            try:
                execute_query(
                    """INSERT INTO order_items
                       (order_id, cod_art, qta_ordinata, source, last_updated_by,
                        ai_confidence, related_message_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    params,
                    fetch=False,
                )
            except pg_errors.UniqueViolation as exc:
                constraint_name = getattr(getattr(exc, "diag", None), "constraint_name", None)
                if constraint_name != "order_items_pkey":
                    raise

                self._resync_id_sequence("order_items")
                execute_query(
                    """INSERT INTO order_items
                       (order_id, cod_art, qta_ordinata, source, last_updated_by,
                        ai_confidence, related_message_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    params,
                    fetch=False,
                )

        # Chiudi la sessione associata
        if session_id:
            execute_query(
                "UPDATE chat_sessions SET status = 'completed', closed_at = NOW() WHERE id = %s",
                (session_id,),
                fetch=False,
            )

        return order_id

    def get_orders_by_client(self, cod_cli: int, page: int = 0,
                             limit: int = 15) -> list[dict]:
        offset = page * limit
        return execute_query(
            """SELECT
                 o.id AS order_id,
                 o.data_ord,
                 o.session_id,
                 (SELECT COUNT(DISTINCT oi.id) FROM order_items oi WHERE oi.order_id = o.id) AS item_count,
                 (SELECT COALESCE(SUM(oi.qta_ordinata), 0) FROM order_items oi WHERE oi.order_id = o.id) AS total_qty,
                 (SELECT COUNT(*) FROM chat_messages cm WHERE cm.session_id = o.session_id) AS message_count,
                 (
                   SELECT json_agg(sub)
                   FROM (
                     SELECT oi2.cod_art, a.des_art, oi2.qta_ordinata
                     FROM order_items oi2
                     LEFT JOIN anaart a ON a.cod_art = oi2.cod_art
                     WHERE oi2.order_id = o.id
                     ORDER BY oi2.id ASC
                     LIMIT 3
                   ) sub
                 ) AS preview_items
               FROM (
                 SELECT id, data_ord, session_id
                 FROM orders
                 WHERE cod_cli = %s
                 ORDER BY data_ord DESC, id DESC
                 LIMIT %s OFFSET %s
               ) o
               ORDER BY o.data_ord DESC, o.id DESC""",
            (cod_cli, limit, offset),
        )

    def get_order_detail(self, order_id: int, cod_cli: int) -> Optional[dict]:
        # Header
        order = execute_query_one(
            """SELECT id, cod_cli, user_id, session_id, data_ord
               FROM orders WHERE id = %s AND cod_cli = %s""",
            (order_id, cod_cli),
        )
        if not order:
            return None

        # Items
        items = execute_query(
            """SELECT oi.id, oi.cod_art, oi.qta_ordinata, oi.source, oi.last_updated_by,
                      oi.ai_confidence, oi.related_message_id,
                      a.des_art, a.des_um, a.pezzi_conf, a.des_tipo_um, a.linea, a.famiglia
               FROM order_items oi
               LEFT JOIN anaart a ON oi.cod_art = a.cod_art
               WHERE oi.order_id = %s
               ORDER BY oi.id ASC""",
            (order_id,),
        )

        # Messages (se c'è una sessione associata)
        messages = []
        if order.get("session_id"):
            messages = execute_query(
                """SELECT id, sender, content, metadata, created_at
                   FROM chat_messages
                   WHERE session_id = %s
                   ORDER BY created_at ASC""",
                (order["session_id"],),
            )

        return {
            "order_id": order["id"],
            "cod_cli": order["cod_cli"],
            "data_ord": order["data_ord"],
            "session_id": order["session_id"],
            "items": items,
            "messages": messages,
        }

    # =======================================================================
    # Metodi aggiuntivi — Prodotti e Feedback
    # =======================================================================

    def search_products(self, query: str, cod_cli: int, limit: int = 20) -> list[dict]:
        """Ricerca prodotti con filtro assortimento e status bloccanti."""
        search_term = f"%{query}%"

        # Costruisci condizioni per status bloccanti
        status_conditions = " OR ".join(
            f"UPPER(stato) LIKE %s" for _ in BLOCKING_STATUSES
        )
        status_params = [f"{s}%" for s in BLOCKING_STATUSES]

        sql = f"""
            SELECT cod_art, des_art, des_um, pezzi_conf, des_tipo_um, stato,
                   linea, famiglia
            FROM anaart
            WHERE (des_art ILIKE %s OR cod_art ILIKE %s)
            AND (
                NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s)
                OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s AND cod_art = anaart.cod_art)
            )
            AND (stato IS NULL OR NOT ({status_conditions}))
            ORDER BY des_art ASC
            LIMIT %s
        """
        params = [search_term, search_term, cod_cli, cod_cli] + status_params + [limit]
        return execute_query(sql, params)

    def save_feedback(self, message_id: int, user_id: int, is_positive: bool,
                      reason_category: Optional[str] = None,
                      comment: Optional[str] = None) -> Optional[int]:
        """Salva o aggiorna un feedback senza vincolo unique su (message_id, user_id)."""
        existing = execute_query_one(
            """SELECT id FROM message_feedbacks
               WHERE message_id = %s AND user_id = %s
               ORDER BY id DESC LIMIT 1""",
            (message_id, user_id),
        )

        if existing:
            row = execute_query_one(
                """UPDATE message_feedbacks
                   SET is_positive = %s,
                       reason_category = %s,
                       comment = %s,
                       created_at = NOW()
                   WHERE id = %s
                   RETURNING id""",
                (is_positive, reason_category, comment, existing["id"]),
            )
            return row["id"] if row else None

        row = execute_query_one(
            """INSERT INTO message_feedbacks (message_id, user_id, is_positive, reason_category, comment)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id""",
            (message_id, user_id, is_positive, reason_category, comment),
        )
        return row["id"] if row else None

    def delete_feedback(self, message_id: int, user_id: int) -> bool:
        """Elimina un feedback."""
        result = execute_query(
            "DELETE FROM message_feedbacks WHERE message_id = %s AND user_id = %s RETURNING id",
            (message_id, user_id),
        )
        return len(result) > 0

    # --- DB Service methods migrated from services/db_service.py ---

    def search_products_for_ai(self, search_term: str, cod_cli: int,
                               limit: int = 5) -> list[dict]:
        """Ricerca prodotti per l'AI (usata dal ConversationService)."""
        return execute_query(
            """SELECT a.cod_art, a.des_art, a.des_um, a.pezzi_conf, a.des_tipo_um
               FROM anaart a
               INNER JOIN asscli ac ON a.cod_art = ac.cod_art AND ac.cod_cli = %s
               WHERE (a.des_art ILIKE %s OR a.cod_art ILIKE %s)
               AND (a.stato IS NULL OR UPPER(a.stato) NOT LIKE 'ARTICOLO SOSPESO%%')
               LIMIT %s""",
            (cod_cli, f"%{search_term}%", f"%{search_term}%", limit),
        )

    def get_cart_by_client(self, client_id: int,
                           session_id: Optional[int] = None) -> list[dict]:
        """Recupera il carrello per il contesto AI (intent EDIT)."""
        if session_id:
            return execute_query(
                """SELECT ci.id, ci.cod_art, ci.qta, a.des_art
                   FROM cart_items ci
                   LEFT JOIN anaart a ON ci.cod_art = a.cod_art
                   WHERE ci.session_id = %s
                   ORDER BY ci.id""",
                (session_id,),
            )
        return execute_query(
            """SELECT ci.id, ci.cod_art, ci.qta, a.des_art
               FROM cart_items ci
               LEFT JOIN anaart a ON ci.cod_art = a.cod_art
               WHERE ci.session_id IN (
                   SELECT cs.id FROM chat_sessions cs
                   JOIN app_users au ON au.id = cs.user_id
                   WHERE au.cod_cli = %s AND cs.status = 'active'
                   ORDER BY cs.created_at DESC LIMIT 1
               )
               ORDER BY ci.id""",
            (client_id,),
        )

    def get_order_history_flat(self, cod_cli: int, limit: int = 10) -> list[dict]:
        """Storico ordini flat (per 'il solito' — una riga per articolo ordinato)."""
        return execute_query(
            """SELECT oi.cod_art, a.des_art, o.data_ord, oi.qta_ordinata, a.des_um
               FROM orders o
               JOIN order_items oi ON oi.order_id = o.id
               LEFT JOIN anaart a ON oi.cod_art = a.cod_art
               WHERE o.cod_cli = %s
               ORDER BY o.data_ord DESC, o.id DESC, oi.id ASC
               LIMIT %s""",
            (cod_cli, limit),
        )

    def get_available_cod_art(self, cod_cli: int, limit: int = 500) -> list[str]:
        """Codici articolo disponibili per il cliente (assortimento + stato)."""
        rows = execute_query(
            """SELECT cod_art FROM anaart
               WHERE (
                   NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s)
                   OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s AND cod_art = anaart.cod_art)
               )
               AND (stato IS NULL OR stato NOT IN ('ARTICOLO SOSPESO', 'SU AUTORIZZAZIONE', 'DISPONIBILE DAL'))
               LIMIT %s""",
            (cod_cli, cod_cli, limit),
        )
        return [r["cod_art"] for r in rows if r.get("cod_art")]

    def get_last_orders(self, cod_cli: int, limit: int = 3) -> list[dict]:
        """Recupera gli ultimi ordini per l'AI context."""
        return execute_query(
            """SELECT o.id, o.data_ord,
                      json_agg(json_build_object(
                          'cod_art', oi.cod_art,
                          'des_art', a.des_art,
                          'qta', oi.qta_ordinata
                      )) AS items
               FROM orders o
               JOIN order_items oi ON o.id = oi.order_id
               LEFT JOIN anaart a ON oi.cod_art = a.cod_art
               WHERE o.cod_cli = %s
               GROUP BY o.id, o.data_ord
               ORDER BY o.data_ord DESC
               LIMIT %s""",
            (cod_cli, limit),
        )
