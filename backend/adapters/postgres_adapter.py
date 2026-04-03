from typing import Optional
import json
from psycopg2 import errors as pg_errors

from ports.i_user_repository import IUserRepository
from ports.i_session_manager import ISessionManager
from ports.i_order_repository import IOrderRepository
from ports.i_ticket_repository import ITicketRepository
from adapters.database import execute_query, execute_query_one

BLOCKING_STATUSES = [
    "ARTICOLO SOSPESO",
    "SU AUTORIZZAZIONE",
    "DISPONIBILE DAL",
    "NON DISPONIBILE",
]

class PostgresAdapter(IUserRepository, ISessionManager, IOrderRepository, ITicketRepository):
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

    def get_cart_by_session(self, session_id: int) -> list[dict]:
        """Recupera gli articoli nel carrello di una sessione specifica."""
        return execute_query(
            """SELECT ci.id, ci.cod_art, ci.qta, ci.source, ci.last_updated_by,
                      ci.ai_confidence, ci.related_message_id, ci.updated_at,
                      a.des_art, a.des_um, a.pezzi_conf, a.des_tipo_um,
                      a.linea, a.famiglia, a.stato
               FROM cart_items ci
               LEFT JOIN anaart a ON ci.cod_art = a.cod_art
               WHERE ci.session_id = %s
               ORDER BY ci.updated_at ASC""",
            (session_id,),
        )

    def get_cart(self, user_id: int) -> list[dict]:
        session = self.get_active_session(user_id)
        if not session:
            return []
        return self.get_cart_by_session(session["id"])

    def _validate_product_exists(self, cod_art: str) -> None:
        product_exists = execute_query_one(
            "SELECT cod_art FROM anaart WHERE cod_art = %s LIMIT 1",
            (cod_art,),
        )
        if not product_exists:
            raise ValueError(f"Articolo non valido: {cod_art}")

    def add_to_cart(self, user_id: int, cod_art: str, qta: int,
                    source: str = "customer",
                    ai_confidence: Optional[float] = None,
                    related_message_id: Optional[int] = None) -> dict:
        session = self.get_active_session(user_id)
        if not session:
            # Crea sessione se non esiste
            session = self.create_session(user_id)

        return self.add_to_cart_by_session(
            session_id=session["id"],
            cod_art=cod_art,
            qta=qta,
            source=source,
            ai_confidence=ai_confidence,
            related_message_id=related_message_id,
        )

    def add_to_cart_by_session(self, session_id: int, cod_art: str, qta: int,
                               source: str = "customer",
                               ai_confidence: Optional[float] = None,
                               related_message_id: Optional[int] = None) -> dict:
        self._validate_product_exists(cod_art)

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
        if not session:
            return False
        return self.remove_from_cart_by_session(cart_item_id, session["id"])

    def remove_from_cart_by_session(self, cart_item_id: int, session_id: int) -> bool:
        result = execute_query(
            "DELETE FROM cart_items WHERE id = %s AND session_id = %s RETURNING id",
            (cart_item_id, session_id),
        )
        return len(result) > 0

    def update_cart_quantity(self, cart_item_id: int, user_id: int,
                            qta: int, source: str = "customer") -> bool:
        session = self.get_active_session(user_id)
        if not session:
            return False
        return self.update_cart_quantity_by_session(cart_item_id, session["id"], qta, source)

    def update_cart_quantity_by_session(self, cart_item_id: int, session_id: int,
                                        qta: int, source: str = "customer") -> bool:
        result = execute_query(
            """UPDATE cart_items SET qta = %s, source = %s, last_updated_by = %s
               WHERE id = %s AND session_id = %s RETURNING id""",
            (qta, source, source, cart_item_id, session_id),
        )
        return len(result) > 0

    def clear_cart(self, user_id: int) -> None:
        session = self.get_active_session(user_id)
        if not session:
            return
        self.clear_cart_by_session(session["id"])

    def clear_cart_by_session(self, session_id: int) -> None:
        execute_query(
            "DELETE FROM cart_items WHERE session_id = %s",
            (session_id,),
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

    def _build_order_conditions(self, base_where: str, params: list,
                                 search: str, date_from: Optional[str],
                                 date_to: Optional[str],
                                 extra_joins: str = "") -> tuple[str, list]:
        """Helper per costruire WHERE clause condizionali."""
        conditions = []
        p = list(params)

        if search:
            conditions.append("CAST(o.id AS TEXT) ILIKE %s")
            p.append(f"%{search}%")

        if date_from:
            conditions.append("o.data_ord >= %s::date")
            p.append(date_from)

        if date_to:
            conditions.append("o.data_ord <= %s::date")
            p.append(date_to)

        if conditions:
            where = extra_joins + " WHERE " + base_where + " AND " + " AND ".join(conditions)
        else:
            where = extra_joins + " WHERE " + base_where

        return where, p

    def _safe_sort(self, sort_by: str, sort_dir: str, allowed: list[str]) -> tuple[str, str]:
        col = sort_by if sort_by in allowed else "data_ord"
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        return col, direction

    def get_orders_by_client(self, cod_cli: int, page: int = 0,
                             limit: int = 15,
                             search: str = "",
                             sort_by: str = "data_ord",
                             sort_dir: str = "desc",
                             date_from: Optional[str] = None,
                             date_to: Optional[str] = None) -> list[dict]:
        offset = page * limit
        sort_col, sort_dir_san = self._safe_sort(sort_by, sort_dir, ["data_ord", "id", "item_count"])

        base_where = "cod_cli = %s"
        params = [cod_cli]

        where_clause, query_params = self._build_order_conditions(
            base_where, params, search, date_from, date_to
        )

        order_clause = f"ORDER BY o.{sort_col} {sort_dir_san}, o.id {sort_dir_san}"

        return execute_query(
            f"""SELECT
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
                 {where_clause}
                 {order_clause}
                 LIMIT %s OFFSET %s
               ) o
               {order_clause}""",
            query_params + [limit, offset],
        )

    def get_all_orders(self, page: int = 0, limit: int = 15,
                       search: str = "",
                       sort_by: str = "data_ord",
                       sort_dir: str = "desc",
                       date_from: Optional[str] = None,
                       date_to: Optional[str] = None,
                       search_cod_cli: str = "",
                       search_rag_soc: str = "") -> list[dict]:
        offset = page * limit
        sort_col, sort_dir_san = self._safe_sort(sort_by, sort_dir, ["data_ord", "id", "cod_cli", "rag_soc", "item_count"])

        conditions = []
        params: list = []

        if search:
            conditions.append("CAST(o.id AS TEXT) ILIKE %s")
            params.append(f"%{search}%")
        if date_from:
            conditions.append("o.data_ord >= %s::date")
            params.append(date_from)
        if date_to:
            conditions.append("o.data_ord <= %s::date")
            params.append(date_to)
        if search_cod_cli:
            conditions.append("CAST(o.cod_cli AS TEXT) ILIKE %s")
            params.append(f"%{search_cod_cli}%")
        if search_rag_soc:
            conditions.append("LOWER(an.rag_soc) LIKE LOWER(%s)")
            params.append(f"%{search_rag_soc}%")

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        order_clause = f"ORDER BY o.{sort_col} {sort_dir_san}, o.id {sort_dir_san}"

        return execute_query(
            f"""SELECT
                 o.id AS order_id,
                 o.data_ord,
                 o.session_id,
                 o.cod_cli,
                 an.rag_soc,
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
               FROM orders o
               LEFT JOIN anacli an ON o.cod_cli = an.cod_cli
               {where_clause}
               {order_clause}
               LIMIT %s OFFSET %s""",
            params + [limit, offset],
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

    # =======================================================================
    # ITicketRepository
    # =======================================================================

    def create_ticket(self, session_id: int, cod_cli: int) -> dict:
        row = execute_query_one(
            """INSERT INTO tickets (session_id, cod_cli, status)
               VALUES (%s, %s, 'aperto')
               RETURNING id, session_id, cod_cli, status, locked_by, created_at, updated_at""",
            (session_id, cod_cli),
        )
        return row  # type: ignore

    def get_ticket_by_session(self, session_id: int, cod_cli: Optional[int] = None) -> Optional[dict]:
        if cod_cli is not None:
            return execute_query_one(
                """SELECT id, session_id, cod_cli, status, locked_by, created_at, updated_at
                   FROM tickets
                   WHERE session_id = %s
                     AND cod_cli = %s
                     AND status != 'chiuso'
                   ORDER BY created_at DESC LIMIT 1""",
                (session_id, cod_cli),
            )
        return execute_query_one(
            """SELECT id, session_id, cod_cli, status, locked_by, created_at, updated_at
               FROM tickets
               WHERE session_id = %s
                 AND status != 'chiuso'
               ORDER BY created_at DESC LIMIT 1""",
            (session_id,),
        )

    def get_open_tickets(self) -> list[dict]:
        return execute_query(
            """SELECT id, session_id, cod_cli, status, locked_by, created_at, updated_at
               FROM tickets
               WHERE status IN ('aperto', 'in_lavorazione')
               ORDER BY created_at ASC""",
            (),
        )

    def get_ticket_by_id(self, ticket_id: int) -> Optional[dict]:
        return execute_query_one(
            """SELECT id, session_id, cod_cli, status, locked_by, created_at, updated_at
               FROM tickets WHERE id = %s LIMIT 1""",
            (ticket_id,),
        )

    def lock_ticket(self, ticket_id: int, operator_id: int) -> bool:
        result = execute_query(
            """UPDATE tickets
               SET status = 'in_lavorazione',
                   locked_by = %s,
                   updated_at = NOW()
               WHERE id = %s
                 AND status != 'chiuso'
               RETURNING id, session_id""",
            (operator_id, ticket_id),
        )
        if result:
            session_id = result[0].get("session_id")
            if session_id:
                self._save_system_message(session_id, "Un operatore ha preso in carico il ticket di assistenza.")
        return len(result) > 0

    def unlock_ticket(self, ticket_id: int) -> None:
        row = execute_query_one(
            """UPDATE tickets
               SET locked_by = NULL, updated_at = NOW()
               WHERE id = %s
               RETURNING session_id""",
            (ticket_id,),
        )
        if row and row.get("session_id"):
            self._save_system_message(row["session_id"], "L'operatore ha rilasciato il ticket. Puoi continuare a chattare.")
        else:
            execute_query(
                """UPDATE tickets
                   SET locked_by = NULL, updated_at = NOW()
                   WHERE id = %s""",
                (ticket_id,),
                fetch=False,
            )

    def close_ticket(self, ticket_id: int) -> None:
        row = execute_query_one(
            """UPDATE tickets
               SET status = 'chiuso', locked_by = NULL, updated_at = NOW()
               WHERE id = %s
               RETURNING session_id""",
            (ticket_id,),
        )
        if row and row.get("session_id"):
            self._save_system_message(row["session_id"], "Il ticket di assistenza è stato chiuso. L'assistente AI è di nuovo disponibile per questa sessione.")
        else:
            execute_query(
                """UPDATE tickets
                   SET status = 'chiuso', locked_by = NULL, updated_at = NOW()
                   WHERE id = %s""",
                (ticket_id,),
                fetch=False,
            )

    def _save_system_message(self, session_id: int, content: str) -> None:
        """Helper interno per salvare messaggi di sistema nella chat."""
        try:
            execute_query(
                """INSERT INTO chat_messages (session_id, sender, content)
                   VALUES (%s, 'system', %s)""",
                (session_id, content),
                fetch=False,
            )
        except Exception:
            pass  # Non fallire l'operazione principale se il messaggio non si salva

    def get_last_message_time(self, session_id: int) -> Optional[str]:
        row = execute_query_one(
            """SELECT created_at FROM chat_messages
               WHERE session_id = %s
               ORDER BY created_at DESC LIMIT 1""",
            (session_id,),
        )
        return row["created_at"] if row else None

    def send_message(self, session_id: int, sender: str, content: str) -> int:
        """Salva un messaggio nella chat (operator o customer)."""
        row = execute_query_one(
            """INSERT INTO chat_messages (session_id, sender, content)
               VALUES (%s, %s, %s)
               RETURNING id""",
            (session_id, sender, content),
        )
        return row["id"]  # type: ignore
