import asyncio
import csv
import json
import os
from typing import Optional
from ports.i_order_repository import IOrderRepository
from ports.i_session_manager import ISessionManager

class OrderService:
    def __init__(self, order_repo: IOrderRepository, session_manager: ISessionManager,
                 broadcaster=None):
        self._repo = order_repo
        self._session_manager = session_manager
        self._broadcaster = broadcaster

    def _schedule_emit(self, coro) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
            return
        loop.create_task(coro)

    def create_order(self, cod_cli: int, user_id: int,
                     session_id: Optional[int], items: list[dict]) -> int:
        order_id = self._repo.create_order(cod_cli, user_id, session_id, items)
        # Svuota il carrello dopo la creazione dell'ordine
        if session_id:
            self._session_manager.clear_cart_by_session(session_id)
        else:
            self._session_manager.clear_cart(user_id)
        # Notifica SSE per aggiornare il carrello in tempo reale
        if self._broadcaster and session_id:
            self._schedule_emit(
                self._broadcaster.emit(session_id, "cart_update", {"action": "cleared"})
            )
        return order_id

    def get_orders_by_client(self, cod_cli: int, page: int = 0, limit: int = 15,
                             search: str = "", sort_by: str = "data_ord",
                             sort_dir: str = "desc",
                             date_from: Optional[str] = None,
                             date_to: Optional[str] = None) -> list[dict]:
        return self._repo.get_orders_by_client(
            cod_cli, page, limit, search, sort_by, sort_dir, date_from, date_to)

    def get_all_orders(self, page: int = 0, limit: int = 15,
                      search: str = "", sort_by: str = "data_ord",
                      sort_dir: str = "desc",
                      date_from: Optional[str] = None,
                      date_to: Optional[str] = None,
                      search_cod_cli: str = "",
                      search_rag_soc: str = "",
                      esportato: Optional[bool] = None) -> list[dict]:
        return self._repo.get_all_orders(
            page, limit, search, sort_by, sort_dir, date_from, date_to,
            search_cod_cli, search_rag_soc, esportato)

    def get_order_detail(self, order_id: int, cod_cli: int) -> Optional[dict]:
        return self._repo.get_order_detail(order_id, cod_cli)

    def _write_export_file(self, folder: str, order_id: int,
                           detail: dict, fmt: str) -> str:
        """Scrive il file JSON o CSV di un ordine. Ritorna il filepath."""
        os.makedirs(folder, exist_ok=True)
        data_ord = detail.get("data_ord")
        if data_ord:
            if hasattr(data_ord, 'strftime'):
                safe_date = data_ord.strftime("%Y%m%d")
            else:
                safe_date = str(data_ord)[:10].replace("-", "")
        else:
            safe_date = "nodate"
        filename = f"ordine_{order_id}_{safe_date}.{fmt}"
        filepath = os.path.join(folder, filename)

        if fmt == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(detail, f, ensure_ascii=False, indent=2, default=str)
        else:  # csv
            with open(filepath, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["cod_art", "des_art", "qta_ordinata", "des_um",
                                 "linea", "famiglia", "source", "ai_confidence"])
                for item in detail.get("items", []):
                    writer.writerow([
                        item.get("cod_art", ""),
                        item.get("des_art", ""),
                        item.get("qta_ordinata", ""),
                        item.get("des_um", ""),
                        item.get("linea", ""),
                        item.get("famiglia", ""),
                        item.get("source", ""),
                        item.get("ai_confidence", ""),
                    ])
        return filepath

    def export_order(self, order_id: int, user_id: int,
                     fmt: str = "json") -> Optional[dict]:
        """Esporta un ordine in JSON o CSV nella cartella configurata dall'operatore.

        Args:
            order_id: ID dell'ordine da esportare.
            user_id: ID dell'operatore (per recuperare la sua export_folder).
            fmt: Formato file — 'json' (default) o 'csv'.
        Returns:
            dict con file_path, filename, format oppure None se l'ordine non esiste.
        Raises:
            ValueError: se la cartella di export non è configurata.
        """
        from ports.i_user_repository import IUserRepository
        user_repo: IUserRepository = self._repo  # type: ignore

        folder = user_repo.get_export_folder(user_id)
        if not folder:
            raise ValueError("Cartella di esportazione non configurata nel profilo")

        detail = self._repo.get_order_detail_any(order_id)
        if not detail:
            return None

        filepath = self._write_export_file(folder, order_id, detail, fmt)
        self._repo.mark_order_exported(order_id)

        return {
            "file_path": filepath,
            "filename": os.path.basename(filepath),
            "format": fmt,
        }

    def export_batch(self, user_id: int,
                    date_from: Optional[str] = None,
                    date_to: Optional[str] = None,
                    search_cod_cli: str = "",
                    search_rag_soc: str = "",
                    limit: int = 50) -> dict:
        """Esporta in batch tutti gli ordini non ancora esportati.

        Args:
            user_id: ID dell'operatore (per recuperare la sua export_folder).
            limit: Numero massimo di ordini da esportare (default 50).
        Returns:
            dict con exported_count, failed_count, errors.
        Raises:
            ValueError: se la cartella di export non è configurata.
        """
        from ports.i_user_repository import IUserRepository
        user_repo: IUserRepository = self._repo  # type: ignore

        folder = user_repo.get_export_folder(user_id)
        if not folder:
            raise ValueError("Cartella di esportazione non configurata nel profilo")

        # Recupera ordini non esportati, ordinati per data DESC
        orders = self._repo.get_all_orders(
            page=0, limit=limit, sort_by="data_ord", sort_dir="desc",
            date_from=date_from, date_to=date_to,
            search_cod_cli=search_cod_cli, search_rag_soc=search_rag_soc,
            esportato=False,
        )

        exported_ids: list[int] = []
        errors: list[str] = []

        for order in orders:
            order_id = order["order_id"]
            try:
                detail = self._repo.get_order_detail_any(order_id)
                if not detail:
                    errors.append(f"Ordine #{order_id}: non trovato")
                    continue
                self._write_export_file(folder, order_id, detail, "json")
                exported_ids.append(order_id)
            except Exception as e:
                errors.append(f"Ordine #{order_id}: {str(e)}")

        if exported_ids:
            self._repo.mark_orders_exported(exported_ids)

        return {
            "exported_count": len(exported_ids),
            "failed_count": len(errors),
            "errors": errors,
        }
