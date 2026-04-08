from fastapi import APIRouter, Depends, HTTPException
from domain.schemas import FeedbackRequest
from controllers.auth_controller import _get_current_user
from services.feedback_service import FeedbackService

router = APIRouter(tags=["feedback"])


def _get_feedback_service() -> FeedbackService:
    """Factory per DI — iniettata in main.py."""
    raise NotImplementedError("Override in main.py")


@router.post("/feedback")
def handle_feedback(body: FeedbackRequest,
                    user: dict = Depends(_get_current_user),
                    feedback_service: FeedbackService = Depends(_get_feedback_service)):
    # Delete feedback
    if body.action == "delete":
        feedback_service.delete_feedback(body.message_id, user["userId"])
        return {"success": True, "deleted": True}

    # Save/update feedback (upsert)
    if body.is_positive is None:
        raise HTTPException(status_code=400, detail="is_positive obbligatorio")

    safe_comment = str(body.comment)[:500] if body.comment else None
    fb_id = feedback_service.save_feedback(
        message_id=body.message_id,
        user_id=user["userId"],
        is_positive=body.is_positive,
        reason_category=body.reason_category,
        comment=safe_comment,
    )
    return {"success": True, "id": fb_id}
