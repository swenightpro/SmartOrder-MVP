import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Canale speciale per la lista ticket degli operatori (nessuna sessione ha id=0)
OPERATOR_CHANNEL = 0


class SSEBroadcaster:
    """Singleton asyncio-based event broadcaster keyed by session_id."""

    def __init__(self):
        self._subscribers: dict[int, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Subscription Management
    # ------------------------------------------------------------------

    async def subscribe(self, session_id: int) -> asyncio.Queue:
        """Restituisce una nuova coda per la sessione. Il chiamante legge da essa."""
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers[session_id].append(queue)
        logger.info(f"SSE: subscriber added for session_id={session_id}")
        return queue

    async def unsubscribe(self, session_id: int, queue: asyncio.Queue) -> None:
        """Rimuove uno specifico subscriber."""
        async with self._lock:
            if queue in self._subscribers.get(session_id, []):
                self._subscribers[session_id].remove(queue)
                if not self._subscribers[session_id]:
                    del self._subscribers[session_id]
        logger.info(f"SSE: subscriber removed for session_id={session_id}")

    # ------------------------------------------------------------------
    # Event Emission
    # ------------------------------------------------------------------

    async def emit(self, session_id: int, event_type: str, data: Any) -> None:
        """Broadcast di un evento a tutti i subscriber di una sessione."""
        payload = self._format_event(event_type, data)
        async with self._lock:
            queues = list(self._subscribers.get(session_id, []))


        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(f"SSE queue full for session_id={session_id}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_event(event_type: str, data: Any) -> str:
        """Formatta l'evento come stringa SSE."""
        json_data = json.dumps({"event": event_type, "data": data})
        return f"data: {json_data}\n\n"

    @property
    def active_connections(self) -> int:
        """Conta le connessioni SSE attive totali."""
        return sum(len(qs) for qs in self._subscribers.values())


# Singleton a livello di modulo
_broadcaster: Optional[SSEBroadcaster] = None


def get_broadcaster() -> SSEBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = SSEBroadcaster()
    return _broadcaster
