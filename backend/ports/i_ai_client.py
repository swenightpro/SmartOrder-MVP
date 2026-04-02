# ===========================================================================
# ports/i_ai_client.py — Outbound Port per servizi AI
#
# Formalizza il contratto verso i servizi di AI generativa e speech-to-text.
# ===========================================================================

from abc import ABC, abstractmethod
from typing import IO, Optional


class IAIClient(ABC):
    """Contratto verso servizi AI (LLM e speech-to-text)."""

    @abstractmethod
    async def transcribe_audio(self, audio_file: IO[bytes], filename: str) -> str:
        """Converte audio in testo. Ritorna la trascrizione."""
        ...

    @abstractmethod
    async def interpret_intent(self, text: str, context: str,
                               system_prompt: str,
                               model: Optional[str] = None) -> str:
        """Classifica intenti e produce decisione AI. Ritorna la risposta JSON."""
        ...
