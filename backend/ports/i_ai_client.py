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

    @abstractmethod
    def generate_embedding(self, text: str, model: Optional[str] = None) -> list[float]:
        """Genera un embedding vettoriale per il testo fornito. Ritorna una lista di float."""
        ...

    @abstractmethod
    async def analyze_image(self, image_base64: str,
                           conversation_history: list[dict],
                           system_prompt: str) -> dict:
        """Analizza un'immagine con GPT-4o Vision e restituisce OCR + prodotti."""
        ...
