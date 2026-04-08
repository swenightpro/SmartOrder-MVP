from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Depends, Header
import base64
import hashlib
import json
import logging
import time

logger = logging.getLogger(__name__)
from services.sse_broadcaster import OPERATOR_CHANNEL
from domain.schemas import ChatRequest, SaveMessageRequest
from services.conversation_service import ConversationService
from controllers.auth_controller import _get_current_user

router = APIRouter(tags=["conversation"])


def _get_conversation_service() -> ConversationService:
    """Factory per DI — iniettata in main.py."""
    raise NotImplementedError("Override in main.py")


# ---------------------------------------------------------------------------
# Chat AI
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat(body: ChatRequest,
               user: dict = Depends(_get_current_user),
               conv_service: ConversationService = Depends(_get_conversation_service)):
    try:
        result = await conv_service.handle_message(
            message=body.message,
            client_id=body.clientId,
            history=body.history,
            session_id=body.session_id,
            pending_cart_edits=body.pending_cart_edits,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/image")
async def chat_image(
    file: UploadFile = File(...),
    user: dict = Depends(_get_current_user),
    conv_service: ConversationService = Depends(_get_conversation_service),
    request_id: str = Header(None),
):
    """Upload image: Vision OCR -> virtual user message -> handle_message() -> AI response."""
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Formato immagine non supportato. Usa JPEG, PNG o WebP."
        )

    image_bytes = await file.read()
    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="L'immagine supera i 5MB. Riduci la dimensione e riprova."
        )

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Deduplicate: ignore if same image sent within 5 seconds
    img_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
    now = time.time()
    if not hasattr(chat_image, "_last_image_hash"):
        chat_image._last_image_hash = None
        chat_image._last_image_time = 0.0
    if chat_image._last_image_hash == img_hash and (now - chat_image._last_image_time) < 5:
        logger.info(f"[IMAGE] Duplicate ignored (hash={img_hash})")
        return {"success": True, "user_message_id": None, "ai_message_id": None, "response": "Immagine già elaborata."}
    chat_image._last_image_hash = img_hash
    chat_image._last_image_time = now

    logger.info(f"[IMAGE] content_type={file.content_type}, size={len(image_bytes)}, hash={img_hash}")

    session = conv_service.get_active_session(user["userId"])
    if not session:
        session = conv_service.create_session(user["userId"])

    try:
        # Step 1: Vision OCR
        history_rows = conv_service.get_messages(session["id"])
        history = [
            {"role": "user" if r["sender"] == "user" else "assistant",
             "content": r.get("content") or ""}
            for r in history_rows[-10:]
        ]
        system_prompt = (
            "Sei un assistente OCR per ordini B2B di un bar/ristoro italiano.\n"
            "Il cliente invia foto di: liste della spesa scritte a mano, ordini stampati, "
            "foto di prodotti con etichette, o appunti con quantita'.\n\n"
            "COMPITO:\n"
            "1. Estrai TUTTO il testo visibile nell'immagine nel campo extracted_text.\n"
            "2. Da quel testo, identifica ogni prodotto alimentare/bevanda con la quantita'.\n"
            "3. Nel campo name usa il nome ESATTAMENTE come compare nell'immagine.\n"
            "4. Se la grafia e' difficile, fai del tuo meglio e abbassa la confidence.\n\n"
            "Confidence: 0.0=illeggibile, 0.5=incerto, 1.0=chiaramente leggibile."
        )
        ocr_result = None
        extracted_text = ""
        try:
            ocr_result = await conv_service._ai_client.analyze_image(
                image_base64=image_b64,
                conversation_history=history,
                system_prompt=system_prompt,
            )
            extracted_text = ocr_result.get("extracted_text", "") or ""
        except Exception as e:
            logger.error(f"GPT-4o Vision failed: {e}")

        # Step 2: Format virtual user message
        if extracted_text:
            products_list = []
            for p in (ocr_result.get("products", []) or []):
                products_list.append(f"- {p.get('name', '')} (qta: {p.get('quantity', 1)})")
            products_block = "\n\nProdotti rilevati:\n" + "\n".join(products_list) if products_list else ""
            virtual_message = f"Ho letto da questa immagine:\n{extracted_text}{products_block}"
        else:
            # Vision failed or no text — return error directly (no handle_message call)
            user_msg_id = conv_service._db.save_image_message(
                session_id=session["id"],
                sender="user",
                image_base64=image_b64,
                ocr_text="",
                metadata=json.dumps({"type": "image"}),
            )
            if conv_service._broadcaster:
                await conv_service._broadcaster.emit(session["id"], "image_message", {
                    "id": user_msg_id,
                    "sender": "user",
                    "image_data": image_b64,
                    "ocr_text": "",
                })
                await conv_service._broadcaster.emit(OPERATOR_CHANNEL, "image_message", {
                    "id": user_msg_id,
                    "sender": "user",
                    "image_data": image_b64,
                    "ocr_text": "",
                    "session_id": session["id"],
                })
            return {
                "success": False,
                "user_message_id": user_msg_id,
                "ai_message_id": None,
                "error": "Non sono riuscito a leggere l'immagine. Riprova o descrivi cosa ti serve.",
            }

        # Step 3: Save user image message to DB BEFORE handle_message
        user_msg_id = conv_service._db.save_image_message(
            session_id=session["id"],
            sender="user",
            image_base64=image_b64,
            ocr_text=extracted_text,
            metadata=json.dumps({"type": "image"}),
        )

        # Step 4: Emit image_message SSE (customer sees photo)
        if conv_service._broadcaster:
            await conv_service._broadcaster.emit(session["id"], "image_message", {
                "id": user_msg_id,
                "sender": "user",
                "image_data": image_b64,
                "ocr_text": extracted_text,
            })
            await conv_service._broadcaster.emit(OPERATOR_CHANNEL, "image_message", {
                "id": user_msg_id,
                "sender": "user",
                "image_data": image_b64,
                "ocr_text": extracted_text,
                "session_id": session["id"],
            })

        # Step 5: Call handle_message() with virtual message (normal AI flow)
        history_for_ai = history + [{"role": "user", "content": virtual_message}]
        result = await conv_service.handle_message(
            message=virtual_message,
            client_id=user["cod_cli"],
            history=history_for_ai,
            session_id=session["id"],
            pending_cart_edits=None,
        )

        # Step 5b: Persist confirmed ORDER items to cart on backend.
        # This guarantees cart consistency for image flow even if frontend-side
        # auto-add calls fail or are interrupted.
        cart_added_codes: list[str] = []
        cart_failed_codes: list[str] = []
        if result.get("order_confirmed") and isinstance(result.get("product_items"), list):
            product_confidences = result.get("product_confidences") or {}
            for item in result.get("product_items") or []:
                cod_art = str(item.get("cod_art") or "").strip()
                if not cod_art:
                    continue

                qty_raw = item.get("quantity", 1)
                try:
                    qta = int(float(qty_raw))
                    if qta < 1:
                        qta = 1
                except Exception:
                    qta = 1

                confidence = None
                if isinstance(product_confidences, dict):
                    try:
                        confidence = product_confidences.get(cod_art)
                    except Exception:
                        confidence = None

                try:
                    conv_service._db.add_to_cart_by_session(
                        session_id=session["id"],
                        cod_art=cod_art,
                        qta=qta,
                        source="ai",
                        ai_confidence=confidence,
                        related_message_id=result.get("ai_message_id"),
                    )
                    cart_added_codes.append(cod_art)
                except Exception as cart_err:
                    logger.error(f"[IMAGE] cart sync failed for cod_art={cod_art}: {cart_err}")
                    cart_failed_codes.append(cod_art)

            if conv_service._broadcaster and cart_added_codes:
                await conv_service._broadcaster.emit(session["id"], "cart_update", {})

        # Step 6: Save/transmit AI response
        if result.get("ai_message_id"):
            if conv_service._broadcaster:
                await conv_service._broadcaster.emit(session["id"], "message", {
                    "id": result["ai_message_id"],
                    "sender": "ai",
                    "content": result.get("response") or result.get("message") or "",
                })
        else:
            ai_msg_id = conv_service._db.save_message(
                session["id"], "ai", result.get("response") or result.get("message") or ""
            )
            result["ai_message_id"] = ai_msg_id
            if conv_service._broadcaster:
                await conv_service._broadcaster.emit(session["id"], "message", {
                    "id": ai_msg_id,
                    "sender": "ai",
                    "content": result.get("response") or result.get("message") or "",
                })

        # Step 7: Transform to ImageUploadResponse shape
        return {
            "success": True,
            "user_message_id": user_msg_id,
            "ai_message_id": result.get("ai_message_id"),
            "response": result.get("response") or result.get("message") or "",
            "intent": result.get("intent"),
            "product_codes_with_names": result.get("product_codes_with_names"),
            "product_confidences": result.get("product_confidences"),
            "product_items": result.get("product_items"),
            "cart_edits": result.get("cart_edits"),
            "order_confirmed": result.get("order_confirmed"),
            "edit_confirmed": result.get("edit_confirmed"),
            "cart_synced": bool(cart_added_codes or cart_failed_codes),
            "cart_added_codes": cart_added_codes,
            "cart_failed_codes": cart_failed_codes,
        }

    except Exception as e:
        logger.error(f"[IMAGE] Error in chat_image: {e}")
        return {
            "success": False,
            "error": "Non sono riuscito a leggere l'immagine. Riprova o descrivi cosa ti serve.",
        }


# ---------------------------------------------------------------------------
# Trascrizione audio
# ---------------------------------------------------------------------------

@router.post("/chat/save-message")
async def save_message_to_session(
    body: SaveMessageRequest,
    user: dict = Depends(_get_current_user),
    conv_service: ConversationService = Depends(_get_conversation_service),
):
    """Save a UI-originated message (confirmation, error) to the session so it persists across reloads."""
    allowed = {"user", "ai", "system"}
    if body.sender not in allowed:
        raise HTTPException(status_code=400, detail="Invalid sender value")
    msg_id = conv_service.save_message_to_session(body.session_id, body.sender, body.content)
    return {"message_id": msg_id}


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...),
                     conv_service: ConversationService = Depends(_get_conversation_service)):
    try:
        text = await conv_service.transcribe_audio(file.file, file.filename or "audio.webm")
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Sessioni
# ---------------------------------------------------------------------------

@router.get("/sessions")
def get_active_session(user: dict = Depends(_get_current_user),
                       conv_service: ConversationService = Depends(_get_conversation_service)):
    session = conv_service.get_active_session(user["userId"])
    if session:
        return {"session": {"id": session["id"]}}
    return {"session": None}


@router.post("/sessions")
def create_session(user: dict = Depends(_get_current_user),
                   conv_service: ConversationService = Depends(_get_conversation_service)):
    session = conv_service.create_session(user["userId"])
    return {"session": {"id": session["id"]}}


# ---------------------------------------------------------------------------
# Messaggi
# ---------------------------------------------------------------------------

@router.get("/messages")
def get_messages(session_id: int,
                 user: dict = Depends(_get_current_user),
                 conv_service: ConversationService = Depends(_get_conversation_service)):
    messages = conv_service.get_messages_for_user(session_id, user["userId"])
    return {"messages": messages}
