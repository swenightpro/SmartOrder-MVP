from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Depends
from domain.schemas import ChatRequest
from services.conversation_service import ConversationService
from controllers.auth_controller import _get_current_user

router = APIRouter(tags=["conversation"])

def _get_conversation_service() -> ConversationService:
    """Factory per DI — iniettata in main.py."""
    raise NotImplementedError("Override in main.py")

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

@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...),
                     conv_service: ConversationService = Depends(_get_conversation_service)):
    try:
        text = await conv_service.transcribe_audio(file.file, file.filename or "audio.webm")
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@router.get("/messages")
def get_messages(session_id: int,
                 user: dict = Depends(_get_current_user),
                 conv_service: ConversationService = Depends(_get_conversation_service)):
    messages = conv_service.get_messages(session_id)
    return {"messages": messages}
