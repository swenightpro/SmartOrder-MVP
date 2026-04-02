# ===========================================================================
# services/feedback_service.py — Application Service per feedback
# ===========================================================================

from typing import Optional

class FeedbackService:
    def __init__(self, feedback_repo):
        self._repo = feedback_repo

    def save_feedback(self, message_id: int, user_id: int, is_positive: bool,
                      reason_category: Optional[str] = None,
                      comment: Optional[str] = None) -> Optional[int]:
        return self._repo.save_feedback(message_id, user_id, is_positive, reason_category, comment)

    def delete_feedback(self, message_id: int, user_id: int) -> bool:
        return self._repo.delete_feedback(message_id, user_id)
