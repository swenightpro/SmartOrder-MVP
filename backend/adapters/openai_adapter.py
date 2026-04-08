from typing import IO, Optional, Any
from openai import OpenAI
from pydantic import BaseModel, Field

from ports.i_ai_client import IAIClient
from config import get_settings


class _ProductItem(BaseModel):
    name: str          # exact text as read from the image
    quantity: int = 1
    confidence: float = 0.8


class _ImageAnalysisResult(BaseModel):
    extracted_text: str = ""   # full raw text extracted from image
    ai_response: str = ""
    products: list[_ProductItem] = []


class OpenAIAdapter(IAIClient):
    """Adapter concreto verso le API OpenAI (GPT-4o, Whisper)."""

    def __init__(self):
        s = get_settings()
        self._client = OpenAI(api_key=s.openai_api_key)
        self._default_model = s.ai_model
        self._whisper_model = s.whisper_model
        self._embedding_model = s.embedding_model

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
            #temperature=0.1,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or "{}"

    def generate_embedding(self, text: str, model: Optional[str] = None) -> list[float]:
        """Genera un embedding vettoriale per il testo fornito."""
        model_name = model or self._embedding_model
        response = self._client.embeddings.create(
            model=model_name,
            input=text,
        )
        return response.data[0].embedding

    async def analyze_image(self, image_base64: str,
                           conversation_history: list[dict],
                           system_prompt: str) -> dict:
        """Analyze image with GPT-4o Vision and return structured OCR + product data."""
        messages = [{"role": "system", "content": system_prompt}]
        for h in conversation_history[-10:]:
            messages.append({
                "role": h.get("role", "user"),
                "content": h.get("content", "")
            })

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}",
                        "detail": "high",   # high-res OCR for handwritten/printed text
                    }
                },
                {
                    "type": "text",
                    "text": (
                        "Leggi tutto il testo visibile in questa immagine (OCR completo), "
                        "poi estrai ogni prodotto alimentare o bevanda con la quantità indicata. "
                        "Per ogni prodotto usa il nome esattamente come scritto nell'immagine. "
                        "Se la grafia è incerta, fai del tuo meglio e indica confidence bassa."
                    )
                }
            ]
        })

        response = self._client.beta.chat.completions.parse(
            model=self._default_model,
            messages=messages,
            response_format=_ImageAnalysisResult,
            #temperature=0.0,
            max_completion_tokens=2048,
        )
        parsed = response.choices[0].message.parsed
        return {
            "extracted_text": parsed.extracted_text or "",
            "ai_response": parsed.ai_response or "",
            "products": [
                {"name": p.name, "quantity": p.quantity, "confidence": p.confidence}
                for p in (parsed.products or [])
            ]
        }
