from typing import IO, Optional
from openai import OpenAI

from ports.i_ai_client import IAIClient
from config import get_settings

class OpenAIAdapter(IAIClient):
    """Adapter concreto verso le API OpenAI (GPT-4o, Whisper)."""

    def __init__(self):
        s = get_settings()
        self._client = OpenAI(api_key=s.openai_api_key)
        self._default_model = s.ai_model
        self._whisper_model = s.whisper_model

    async def transcribe_audio(self, audio_file: IO[bytes], filename: str) -> str:
        """Trascrizione audio via Whisper."""
        transcript = self._client.audio.transcriptions.create(
            model=self._whisper_model,
            file=(filename, audio_file),
            language="it",
            prompt=(
                "Trascrizione di un messaggio vocale per un ordine commerciale. "
                "L'utente è un agente che ordina prodotti alimentari dell'azienda Ergon. "
                "Potrebbe menzionare nomi di prodotti, quantità e codici articolo."
            ),
        )
        return transcript.text

    async def interpret_intent(self, text: str, context: str,
                               system_prompt: str,
                               model: Optional[str] = None) -> str:
        """Invoca il modello LLM con sistema prompt e contesto."""
        model_name = model or self._default_model
        response = self._client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{context}\n\nUser message: {text}"},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or "{}"
