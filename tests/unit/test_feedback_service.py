import pytest
from unittest.mock import Mock
from services.feedback_service import FeedbackService


class TestFeedbackService:
    """Unit test per FeedbackService (feedback)"""

    @pytest.fixture
    def mock_repo(self):
        """Mock del feedback repository"""
        return Mock()

    @pytest.fixture
    def feedback_service(self, mock_repo):
        """Istanza di FeedbackService con mock"""
        return FeedbackService(mock_repo)

    # ========== Test Save Feedback ==========

    def test_save_feedback_positive(self, feedback_service, mock_repo):
        """Test: save_feedback salva feedback positivo"""
        # Setup
        message_id = 1
        user_id = 123
        is_positive = True
        expected_feedback_id = 456
        
        mock_repo.save_feedback.return_value = expected_feedback_id
        
        # Execute
        result = feedback_service.save_feedback(message_id, user_id, is_positive)
        
        # Verify
        assert result == expected_feedback_id
        mock_repo.save_feedback.assert_called_once_with(
            message_id, user_id, is_positive, None, None
        )

    def test_save_feedback_negative(self, feedback_service, mock_repo):
        """Test: save_feedback salva feedback negativo"""
        # Setup
        message_id = 1
        user_id = 123
        is_positive = False
        expected_feedback_id = 456
        
        mock_repo.save_feedback.return_value = expected_feedback_id
        
        # Execute
        result = feedback_service.save_feedback(message_id, user_id, is_positive)
        
        # Verify
        assert result == expected_feedback_id

    def test_save_feedback_with_reason(self, feedback_service, mock_repo):
        """Test: save_feedback salva feedback con categoria motivo"""
        # Setup
        message_id = 1
        user_id = 123
        is_positive = False
        reason_category = "product_not_found"
        expected_feedback_id = 456
        
        mock_repo.save_feedback.return_value = expected_feedback_id
        
        # Execute
        result = feedback_service.save_feedback(
            message_id, user_id, is_positive,
            reason_category=reason_category
        )
        
        # Verify
        assert result == expected_feedback_id
        mock_repo.save_feedback.assert_called_once_with(
            message_id, user_id, is_positive, reason_category, None
        )

    def test_save_feedback_with_comment(self, feedback_service, mock_repo):
        """Test: save_feedback salva feedback con commento"""
        # Setup
        message_id = 1
        user_id = 123
        is_positive = False
        comment = "La risposta non era corretta"
        expected_feedback_id = 456
        
        mock_repo.save_feedback.return_value = expected_feedback_id
        
        # Execute
        result = feedback_service.save_feedback(
            message_id, user_id, is_positive,
            comment=comment
        )
        
        # Verify
        assert result == expected_feedback_id
        mock_repo.save_feedback.assert_called_once()

    def test_save_feedback_with_all_params(self, feedback_service, mock_repo):
        """Test: save_feedback con tutti i parametri"""
        # Setup
        message_id = 1
        user_id = 123
        is_positive = False
        reason_category = "wrong_product"
        comment = "Non è quello che avevo richiesto"
        expected_feedback_id = 456
        
        mock_repo.save_feedback.return_value = expected_feedback_id
        
        # Execute
        result = feedback_service.save_feedback(
            message_id, user_id, is_positive,
            reason_category=reason_category,
            comment=comment
        )
        
        # Verify
        assert result == expected_feedback_id
        mock_repo.save_feedback.assert_called_once_with(
            message_id, user_id, is_positive, reason_category, comment
        )

    def test_save_feedback_returns_none(self, feedback_service, mock_repo):
        """Test: save_feedback ritorna None se salvataggio fallisce"""
        # Setup
        message_id = 1
        user_id = 123
        is_positive = True
        mock_repo.save_feedback.return_value = None
        
        # Execute
        result = feedback_service.save_feedback(message_id, user_id, is_positive)
        
        # Verify
        assert result is None

    # ========== Test Delete Feedback ==========

    def test_delete_feedback_success(self, feedback_service, mock_repo):
        """Test: delete_feedback rimuove feedback"""
        # Setup
        message_id = 1
        user_id = 123
        mock_repo.delete_feedback.return_value = True
        
        # Execute
        result = feedback_service.delete_feedback(message_id, user_id)
        
        # Verify
        assert result is True
        mock_repo.delete_feedback.assert_called_once_with(message_id, user_id)

    def test_delete_feedback_not_found(self, feedback_service, mock_repo):
        """Test: delete_feedback ritorna False se feedback non trovato"""
        # Setup
        message_id = 999
        user_id = 123
        mock_repo.delete_feedback.return_value = False
        
        # Execute
        result = feedback_service.delete_feedback(message_id, user_id)
        
        # Verify
        assert result is False

    def test_delete_feedback_multiple_calls(self, feedback_service, mock_repo):
        """Test: delete_feedback può essere chiamato più volte per stesso messaggio"""
        # Setup
        message_id = 1
        user_id = 123
        mock_repo.delete_feedback.side_effect = [True, False]  # Prima volta ok, seconda no
        
        # Execute
        result1 = feedback_service.delete_feedback(message_id, user_id)
        result2 = feedback_service.delete_feedback(message_id, user_id)
        
        # Verify
        assert result1 is True
        assert result2 is False
        assert mock_repo.delete_feedback.call_count == 2