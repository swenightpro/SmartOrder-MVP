from __future__ import annotations
from typing import Optional
import json
import base64
from psycopg2 import errors as pg_errors

from ports.i_user_repository import IUserRepository
from ports.i_session_manager import ISessionManager
from ports.i_order_repository import IOrderRepository
from ports.i_ticket_repository import ITicketRepository
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
        rows = execute_query(
            """SELECT id, session_id, sender, content, metadata, created_at,
                      image_data, ocr_text
               FROM chat_messages
               WHERE session_id = %s
               ORDER BY created_at ASC""",
            (session_id,),
        )
        result = []
        for row in rows:
            r = dict(row)
            if r.get("image_data"):
                r["image_data"] = base64.b64encode(r["image_data"]).decode("utf-8")
            else:
                r["image_data"] = None
            result.append(r)
        return result

    def get_messages_with_feedback(self, session_id: int) -> list[dict]:
        """Recupera i messaggi di sessione con feedback in sola lettura per UI operatore."""
        try:
            rows = execute_query(
                """SELECT cm.id, cm.session_id, cm.sender, cm.content, cm.metadata, cm.created_at,
                          cm.image_data, cm.ocr_text,
                          COALESCE(fb.feedbacks, '[]'::json) AS feedbacks
                   FROM chat_messages cm
                   LEFT JOIN LATERAL (
                       SELECT json_agg(
                           json_build_object(
                               'id', latest.id,
                               'user_id', latest.user_id,
                               'is_positive', latest.is_positive,
                               'reason_category', latest.reason_category,
                               'comment', latest.comment,
                               'created_at', latest.created_at
                           )
                           ORDER BY latest.created_at DESC, latest.id DESC
                       ) AS feedbacks
                       FROM (
                           SELECT DISTINCT ON (mf.user_id)
                                  mf.id,
                                  mf.user_id,
                                  mf.is_positive,
                                  mf.reason_category,
                                  mf.comment,
                                  mf.created_at
                           FROM message_feedbacks mf
                           WHERE mf.message_id = cm.id
                           ORDER BY mf.user_id, mf.created_at DESC, mf.id DESC
                       ) latest
                   ) fb ON TRUE
                   WHERE cm.session_id = %s
                   ORDER BY cm.created_at ASC""",
                (session_id,),
            )
        except pg_errors.UndefinedTable:
            # Compatibilita con DB privi della tabella feedback.
            rows = self.get_messages(session_id)
            for row in rows:
                row["feedbacks"] = []
            return rows

        result = []
        for row in rows:
            r = dict(row)
            if r.get("image_data"):
                r["image_data"] = base64.b64encode(r["image_data"]).decode("utf-8")
            else:
                r["image_data"] = None

            feedbacks = r.get("feedbacks")
            if isinstance(feedbacks, str):
                try:
                    feedbacks = json.loads(feedbacks)
                except Exception:
                    feedbacks = []
            r["feedbacks"] = feedbacks if isinstance(feedbacks, list) else []
            result.append(r)

        return result

    def get_messages_with_user_feedback(self, session_id: int, user_id: int) -> list[dict]:
        """Recupera i messaggi con il feedback piu recente dell'utente corrente."""
        try:
            rows = execute_query(
                """SELECT cm.id, cm.session_id, cm.sender, cm.content, cm.metadata, cm.created_at,
                          cm.image_data, cm.ocr_text,
                          CASE
                              WHEN uf.id IS NULL THEN NULL
                              ELSE json_build_object(
                                  'id', uf.id,
                                  'is_positive', uf.is_positive,
                                  'reason_category', uf.reason_category,
                                  'comment', uf.comment,
                                  'created_at', uf.created_at
                              )
                          END AS feedback
                   FROM chat_messages cm
                   LEFT JOIN LATERAL (
                       SELECT mf.id, mf.is_positive, mf.reason_category, mf.comment, mf.created_at
                       FROM message_feedbacks mf
                       WHERE mf.message_id = cm.id AND mf.user_id = %s
                       ORDER BY mf.created_at DESC, mf.id DESC
                       LIMIT 1
                   ) uf ON TRUE
                   WHERE cm.session_id = %s
                   ORDER BY cm.created_at ASC""",
                (user_id, session_id),
            )
        except pg_errors.UndefinedTable:
            rows = self.get_messages(session_id)
            for row in rows:
                row["feedback"] = None
            return rows

        result = []
        for row in rows:
            r = dict(row)
            if r.get("image_data"):
                r["image_data"] = base64.b64encode(r["image_data"]).decode("utf-8")
            else:
                r["image_data"] = None

            feedback = r.get("feedback")
            if isinstance(feedback, str):
                try:
                    feedback = json.loads(feedback)
                except Exception:
                    feedback = None
            r["feedback"] = feedback if isinstance(feedback, dict) else None
            result.append(r)

        return result

    def save_message(self, session_id: int, sender: str, content: str,
                     metadata: Optional[str] = None) -> int:
        row = execute_query_one(
            """INSERT INTO chat_messages (session_id, sender, content, metadata)
               VALUES (%s, %s, %s, %s)
               RETURNING id""",
            (session_id, sender, content, metadata),
        )
        return row["id"]  # type: ignore

    def save_image_message(self, session_id: int, sender: str,
                           image_base64: str, ocr_text: str,
                           metadata: Optional[str] = None) -> int:
        """Save a message with an image and OCR text."""
        import base64 as b64
        from psycopg2 import Binary
        image_bytes = b64.b64decode(image_base64)
        row = execute_query_one(
            """INSERT INTO chat_messages
               (session_id, sender, content, metadata, image_data, ocr_text)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (session_id, sender, "", metadata, Binary(image_bytes), ocr_text),
        )
        return row["id"]  # type: ignore

    def get_message_by_id(self, message_id: int) -> Optional[dict]:
        import base64 as b64
        row = execute_query_one(
            """SELECT id, session_id, sender, content, metadata, created_at,
                      image_data, ocr_text
               FROM chat_messages
               WHERE id = %s LIMIT 1""",
            (message_id,),
        )
        if not row:
            return None
        r = dict(row)
        if r.get("image_data"):
            r["image_data"] = b64.b64encode(r["image_data"]).decode("utf-8")
        else:
            r["image_data"] = None
        return r

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
        inner_order_clause = f"ORDER BY orders.{sort_col} {sort_dir_san}, orders.id {sort_dir_san}"

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
                 {inner_order_clause}
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
                       search_rag_soc: str = "",
                       esportato: Optional[bool] = None) -> list[dict]:
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
        if esportato is not None:
            conditions.append("o.esportato = %s")
            params.append(esportato)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        order_clause = f"ORDER BY o.{sort_col} {sort_dir_san}, o.id {sort_dir_san}"

        # Provo prima con la colonna esportato; se la colonna non esiste ancora,
        # PostgreSQL lancia un errore che catturiamo e ritentiamo senza.
        try:
            return execute_query(
                f"""SELECT
                     o.id AS order_id,
                     o.data_ord,
                     o.session_id,
                     o.cod_cli,
                     an.rag_soc,
                     o.esportato,
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
        except Exception:
            # Colonna esportato assente: ritento senza
            return execute_query(
                f"""SELECT
                     o.id AS order_id,
                     o.data_ord,
                     o.session_id,
                     o.cod_cli,
                     an.rag_soc,
                     FALSE AS esportato,
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
            messages = self.get_messages_with_feedback(order["session_id"])

        return {
            "order_id": order["id"],
            "cod_cli": order["cod_cli"],
            "data_ord": order["data_ord"],
            "session_id": order["session_id"],
            "items": items,
            "messages": messages,
        }

    def get_order_detail_any(self, order_id: int) -> Optional[dict]:
        """Recupera dettaglio ordine senza filtro cod_cli (per admin export)."""
        order = execute_query_one(
            """SELECT id, cod_cli, user_id, session_id, data_ord
               FROM orders WHERE id = %s""",
            (order_id,),
        )
        if not order:
            return None

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

        messages = []
        if order.get("session_id"):
            messages = self.get_messages_with_feedback(order["session_id"])

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

    def find_product_by_name(self, product_name: str, cod_cli: int) -> Optional[dict]:
        """Trova un prodotto tramite fuzzy search sul nome (ILIKE) con filtro assortimento."""
        results = self.find_products_by_name_fuzzy(product_name, cod_cli, limit=1)
        if results:
            results[0]["match_source"] = "name"
            return results[0]
        return None

    def find_products_by_name_fuzzy(
        self, product_name: str, cod_cli: int, limit: int = 5
    ) -> list[dict]:
        """Cerca prodotti per nome restituendo risultati ordinati per qualita di match ILIKE.

        Usa un ORDER BY che privilegia le corrispondenze piu precise:
        1. Nome che inizia con il termine (LIKE 'name%')
        2. Nome che contiene il termine (LIKE '%name%')
        3. Nome che contiene il termine in mezzo
        """
        status_conditions = " OR ".join(
            f"UPPER(stato) LIKE %s" for _ in BLOCKING_STATUSES
        )
        status_params = [f"{s}%" for s in BLOCKING_STATUSES]

        # Build dynamic ORDER BY for match quality ranking
        escaped_name = product_name.replace("%", "\\%").replace("_", "\\_")

        # Base query
        sql = f"""
            SELECT cod_art, des_art, des_um, pezzi_conf, des_tipo_um, stato,
                   linea, famiglia,
                   CASE
                       WHEN des_art ILIKE %s THEN 1
                       WHEN des_art ILIKE %s THEN 2
                       WHEN des_art ILIKE %s THEN 3
                       ELSE 4
                   END AS match_rank
            FROM anaart
            WHERE des_art ILIKE %s
            AND (
                NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s)
                OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s AND cod_art = anaart.cod_art)
            )
            AND (stato IS NULL OR NOT ({status_conditions}))
            ORDER BY match_rank, des_art ASC
            LIMIT %s
        """
        params = (
            [f"{escaped_name}%", f"% {escaped_name}%", f"%{escaped_name}%",
             f"%{product_name}%", cod_cli, cod_cli]
            + status_params + [limit]
        )
        return execute_query(sql, params)

    def find_product_by_name_merged(self, product_name: str, cod_cli: int,
                                    embedding: list[float],
                                    limit: int = 5) -> Optional[dict]:
        """Cerca prodotto via vector search: embedding del nome → similarita.

        Usa l'embedding generato dal nome estratto dall'immagine
        per trovare il prodotto piu simile nel catalogo del cliente.
        Se non ci sono embeddings, cade su ILIKE puro.
        """
        if not self.has_embeddings():
            return self.find_product_by_name(product_name, cod_cli)

        results = self.search_products_vector(embedding, cod_cli, limit=limit)
        if results:
            results[0]["match_source"] = "name_merged"
            return results[0]
        return None

    def find_product_by_code(self, cod_art: str, cod_cli: int) -> Optional[dict]:
        """Trova un prodotto tramite codice articolo con filtro assortimento."""
        result = execute_query_one(
            """SELECT cod_art, des_art, des_um, pezzi_conf, des_tipo_um, stato,
                      linea, famiglia
               FROM anaart
               WHERE cod_art = %s
               AND (
                   NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s)
                   OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s AND cod_art = anaart.cod_art)
               )
               LIMIT 1""",
            (cod_art, cod_cli, cod_cli),
        )
        if result:
            result["match_source"] = "code"
        return result

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
        blocking_conditions = " AND ".join(
            [f"UPPER(a.stato) NOT LIKE '{s}%%'" for s in BLOCKING_STATUSES]
        )
        rows = execute_query(
            f"""SELECT a.cod_art, a.des_art, a.des_um, a.pezzi_conf, a.des_tipo_um
               FROM anaart a
               WHERE (a.des_art ILIKE %s OR a.cod_art ILIKE %s)
               AND (a.stato IS NULL OR ({blocking_conditions}))
               AND (
                   NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s)
                   OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s AND cod_art = a.cod_art)
               )
               LIMIT %s""",
            (f"%{search_term}%", f"%{search_term}%", cod_cli, cod_cli, limit),
        )
        for row in rows:
            row["match_source"] = "ilike_fallback"
        return rows

    def search_products_keyword_no_asscli(self, keywords: list[str],
                                          limit: int = 20) -> list[dict]:
        """Ricerca prodotti SENZA filtro asscli — per verificare se un prodotto
        esiste nel catalogo ma non nell'assortimento del cliente."""
        if not keywords:
            return []

        keyword_conditions = []
        params: list = []

        for kw in keywords:
            kw_lower = kw.lower().strip()
            if not kw_lower:
                continue
            keyword_conditions.append(
                "(a.des_art ILIKE %s OR a.cod_art ILIKE %s)"
            )
            params.extend([f"%{kw_lower}%", f"%{kw_lower}%"])

        if not keyword_conditions:
            return []

        blocking_conditions = " AND ".join(
            [f"UPPER(a.stato) NOT LIKE '{s}%%'" for s in BLOCKING_STATUSES]
        )

        sql = f"""
            SELECT a.cod_art, a.des_art, a.des_um, a.pezzi_conf, a.des_tipo_um
            FROM anaart a
            WHERE ({") AND (".join(keyword_conditions)})
            AND (a.stato IS NULL OR ({blocking_conditions}))
            LIMIT %s"""

        rows = execute_query(sql, params + [limit])
        for row in rows:
            row["match_source"] = "catalog"
        return rows

    def search_products_keyword(self, keywords: list[str], cod_cli: int,
                                limit: int = 20) -> list[dict]:
        """Word-level ILIKE search for exact keyword matching.

        Returns products where ALL keywords appear in des_art or cod_art,
        case-insensitive, order-insensitive, substring, singular/plural aware.
        Returns dicts with match_source='keyword'.
        """
        if not keywords:
            return []

        keyword_conditions = []
        params: list = []

        for kw in keywords:
            kw_lower = kw.lower().strip()
            if not kw_lower:
                continue
            # Primary: exact keyword substring match
            keyword_conditions.append(
                "(a.des_art ILIKE %s OR a.cod_art ILIKE %s)"
            )
            params.extend([f"%{kw_lower}%", f"%{kw_lower}%"])

            # Fallback: strip common Italian plural suffixes
            if kw_lower.endswith("i") and len(kw_lower) > 2:
                plural_fallback = kw_lower[:-1]
                keyword_conditions.append(
                    "(a.des_art ILIKE %s OR a.cod_art ILIKE %s)"
                )
                params.extend([f"%{plural_fallback}%", f"%{plural_fallback}%"])
            elif kw_lower.endswith("e") and len(kw_lower) > 2:
                plural_fallback = kw_lower[:-1]
                keyword_conditions.append(
                    "(a.des_art ILIKE %s OR a.cod_art ILIKE %s)"
                )
                params.extend([f"%{plural_fallback}%", f"%{plural_fallback}%"])

        if not keyword_conditions:
            return []

        blocking_conditions = " AND ".join(
            [f"UPPER(a.stato) NOT LIKE '{s}%%'" for s in BLOCKING_STATUSES]
        )

        sql = f"""
            SELECT a.cod_art, a.des_art, a.des_um, a.pezzi_conf, a.des_tipo_um
            FROM anaart a
            WHERE ({") AND (".join(keyword_conditions)})
            AND (a.stato IS NULL OR ({blocking_conditions}))
            AND (
                NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s)
                OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s AND cod_art = a.cod_art)
            )
            LIMIT %s"""

        rows = execute_query(sql, params + [cod_cli, cod_cli, limit])
        for row in rows:
            row["match_source"] = "keyword"
        return rows

    def get_embedding(self, cod_art: str) -> Optional[list[float]]:
        """Recupera l'embedding vettoriale di un prodotto, o None se non presente."""
        row = execute_query_one(
            """SELECT embedding FROM product_embeddings WHERE cod_art = %s""",
            (cod_art,),
        )
        if row is None:
            return None
        # embedding is stored as a PostgreSQL array (list of floats)
        return list(row["embedding"])

    def upsert_embedding(self, cod_art: str, embedding: list[float]) -> None:
        """Inserisce o aggiorna l'embedding di un prodotto."""
        execute_query(
            """INSERT INTO product_embeddings (cod_art, embedding)
               VALUES (%s, %s::vector)
               ON CONFLICT (cod_art) DO UPDATE SET embedding = EXCLUDED.embedding""",
            (cod_art, embedding),
            fetch=False,
        )

    def search_products_vector(self, query_embedding: list[float],
                               cod_cli: int, limit: int = 20) -> list[dict]:
        """Ricerca prodotti per similarita vettoriale (pgvector cosine similarity)."""
        blocking_conditions = " AND ".join(
            [f"UPPER(a.stato) NOT LIKE '{s}%%'" for s in BLOCKING_STATUSES]
        )
        rows = execute_query(
            f"""SELECT a.cod_art, a.des_art, a.des_um, a.pezzi_conf, a.des_tipo_um,
                       (pe.embedding <=> %s::vector) AS similarity
               FROM anaart a
               INNER JOIN product_embeddings pe ON a.cod_art = pe.cod_art
               WHERE (a.stato IS NULL OR ({blocking_conditions}))
               AND (
                   NOT EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s)
                   OR EXISTS (SELECT 1 FROM asscli WHERE cod_cli = %s AND cod_art = a.cod_art)
               )
               ORDER BY pe.embedding <=> %s::vector
               LIMIT %s""",
            (query_embedding, cod_cli, cod_cli, query_embedding, limit),
        )
        for row in rows:
            row["match_source"] = "vector"
        return rows

    def has_embeddings(self) -> bool:
        """Ritorna True se esiste almeno un embedding nella tabella."""
        row = execute_query_one("""SELECT 1 FROM product_embeddings LIMIT 1""")
        return row is not None

    def get_cart_by_client(self, client_id: int,
                           session_id: Optional[int] = None) -> list[dict]:
        """Recupera il carrello per il contesto AI (intent EDIT)."""
        if session_id:
            return execute_query(
                """SELECT ci.id, ci.cod_art, ci.qta, a.des_art, a.des_um
                   FROM cart_items ci
                   LEFT JOIN anaart a ON ci.cod_art = a.cod_art
                   WHERE ci.session_id = %s
                   ORDER BY ci.id""",
                (session_id,),
            )
        return execute_query(
            """SELECT ci.id, ci.cod_art, ci.qta, a.des_art, a.des_um
               FROM cart_items ci
               LEFT JOIN anaart a ON ci.cod_art = a.cod_art
               WHERE ci.session_id IN (
                   SELECT cs.id FROM chat_sessions cs
                   WHERE cs.user_id = %s AND cs.status = 'active'
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

    def get_platform_usage_overview(self, days: int = 14) -> dict:
        """Metriche aggregate piattaforma per dashboard operatore (sola lettura)."""
        safe_days = max(7, min(int(days), 90))

        kpis = execute_query_one(
            """SELECT
                 (SELECT COUNT(*)::int FROM orders) AS total_orders,
                 (SELECT COUNT(*)::int FROM tickets) AS total_tickets,
                 (SELECT COUNT(*)::int FROM tickets WHERE status IN ('aperto', 'in_lavorazione')) AS open_tickets,
                 (SELECT COUNT(*)::int FROM chat_sessions WHERE status = 'active') AS active_sessions,
                 (SELECT COUNT(*)::int FROM chat_messages) AS total_messages""",
            (),
        ) or {}

        orders_daily = execute_query(
            """SELECT TO_CHAR(d.day::date, 'YYYY-MM-DD') AS day,
                      COALESCE(o.count, 0)::int AS value
               FROM generate_series(
                    CURRENT_DATE - (%s::int - 1) * INTERVAL '1 day',
                    CURRENT_DATE,
                    INTERVAL '1 day'
               ) AS d(day)
               LEFT JOIN (
                    SELECT DATE(data_ord) AS day, COUNT(*)::int AS count
                    FROM orders
                    WHERE data_ord >= CURRENT_DATE - (%s::int - 1) * INTERVAL '1 day'
                    GROUP BY DATE(data_ord)
               ) o ON o.day = d.day::date
               ORDER BY d.day ASC""",
            (safe_days, safe_days),
        )

        tickets_daily = execute_query(
            """SELECT TO_CHAR(d.day::date, 'YYYY-MM-DD') AS day,
                      COALESCE(t.count, 0)::int AS value
               FROM generate_series(
                    CURRENT_DATE - (%s::int - 1) * INTERVAL '1 day',
                    CURRENT_DATE,
                    INTERVAL '1 day'
               ) AS d(day)
               LEFT JOIN (
                    SELECT DATE(created_at) AS day, COUNT(*)::int AS count
                    FROM tickets
                    WHERE created_at >= CURRENT_DATE - (%s::int - 1) * INTERVAL '1 day'
                    GROUP BY DATE(created_at)
               ) t ON t.day = d.day::date
               ORDER BY d.day ASC""",
            (safe_days, safe_days),
        )

        status_rows = execute_query(
            """SELECT status, COUNT(*)::int AS count
               FROM tickets
               GROUP BY status""",
            (),
        )
        status_totals = {
            "aperto": 0,
            "in_lavorazione": 0,
            "chiuso": 0,
        }
        for row in status_rows:
            key = str(row.get("status") or "")
            if key in status_totals:
                status_totals[key] = int(row.get("count") or 0)

        ticket_status = [
            {"status": "aperto", "label": "Aperti", "count": status_totals["aperto"]},
            {"status": "in_lavorazione", "label": "In lavorazione", "count": status_totals["in_lavorazione"]},
            {"status": "chiuso", "label": "Chiusi", "count": status_totals["chiuso"]},
        ]

        top_clients = execute_query(
            """SELECT o.cod_cli,
                      COALESCE(an.rag_soc, CONCAT('Cliente ', o.cod_cli::text)) AS rag_soc,
                      COUNT(*)::int AS orders
               FROM orders o
               LEFT JOIN anacli an ON an.cod_cli = o.cod_cli
               WHERE o.data_ord >= NOW() - INTERVAL '30 days'
               GROUP BY o.cod_cli, an.rag_soc
               ORDER BY orders DESC, o.cod_cli ASC
               LIMIT 8""",
            (),
        )

        generated_at_row = execute_query_one(
            "SELECT NOW()::text AS generated_at",
            (),
        ) or {}

        return {
            "generated_at": generated_at_row.get("generated_at"),
            "range_days": safe_days,
            "kpis": {
                "total_orders": int(kpis.get("total_orders") or 0),
                "total_tickets": int(kpis.get("total_tickets") or 0),
                "open_tickets": int(kpis.get("open_tickets") or 0),
                "active_sessions": int(kpis.get("active_sessions") or 0),
                "total_messages": int(kpis.get("total_messages") or 0),
            },
            "orders_daily": orders_daily,
            "tickets_daily": tickets_daily,
            "ticket_status": ticket_status,
            "top_clients": top_clients,
        }

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
        return len(result) > 0

    def unlock_ticket(self, ticket_id: int) -> None:
        row = execute_query_one(
            """UPDATE tickets
               SET status = 'aperto', locked_by = NULL, updated_at = NOW()
               WHERE id = %s AND status != 'chiuso'
               RETURNING session_id""",
            (ticket_id,),
        )
        if not row:
            execute_query(
                """UPDATE tickets
                   SET status = 'aperto', locked_by = NULL, updated_at = NOW()
                   WHERE id = %s AND status != 'chiuso'""",
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
        if not row:
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

    def get_export_folder(self, user_id: int) -> Optional[str]:
        row = execute_query_one(
            "SELECT export_folder FROM app_users WHERE id = %s LIMIT 1",
            (user_id,),
        )
        return row.get("export_folder") if row else None

    def set_export_folder(self, user_id: int, path: Optional[str]) -> None:
        execute_query(
            "UPDATE app_users SET export_folder = %s, updated_at = NOW() WHERE id = %s",
            (path, user_id),
            fetch=False,
        )

    def mark_order_exported(self, order_id: int) -> None:
        # Idempotent: aggiunge la colonna se non esiste (prima esecuzione)
        try:
            execute_query(
                "ALTER TABLE orders ADD COLUMN IF NOT EXISTS esportato BOOLEAN NOT NULL DEFAULT FALSE",
                fetch=False,
            )
        except Exception:
            pass  # colonna già esiste
        execute_query(
            "UPDATE orders SET esportato = TRUE WHERE id = %s",
            (order_id,),
            fetch=False,
        )

    def mark_orders_exported(self, order_ids: list[int]) -> None:
        if not order_ids:
            return
        try:
            execute_query(
                "ALTER TABLE orders ADD COLUMN IF NOT EXISTS esportato BOOLEAN NOT NULL DEFAULT FALSE",
                fetch=False,
            )
        except Exception:
            pass
        execute_query(
            "UPDATE orders SET esportato = TRUE WHERE id = ANY(%s)",
            (order_ids,),
            fetch=False,
        )

    def send_message(self, session_id: int, sender: str, content: str) -> int:
        """Salva un messaggio nella chat (operator o customer)."""
        row = execute_query_one(
            """INSERT INTO chat_messages (session_id, sender, content)
               VALUES (%s, %s, %s)
               RETURNING id""",
            (session_id, sender, content),
        )
        return row["id"]  # type: ignore
