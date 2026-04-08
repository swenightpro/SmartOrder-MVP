-- ============================================================================
-- Migration: Add message_feedbacks table for AI response feedback persistence
-- Run: psql -h localhost -U postgres -d smartorder -f migrations/add_message_feedbacks.sql
-- ============================================================================

CREATE TABLE IF NOT EXISTS message_feedbacks (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    is_positive BOOLEAN NOT NULL,
    reason_category VARCHAR(100),
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_message_feedbacks_message_id
    ON message_feedbacks(message_id);

CREATE INDEX IF NOT EXISTS idx_message_feedbacks_user_id
    ON message_feedbacks(user_id);

CREATE INDEX IF NOT EXISTS idx_message_feedbacks_message_user_created
    ON message_feedbacks(message_id, user_id, created_at DESC);

COMMENT ON TABLE message_feedbacks IS 'Feedback utente sui messaggi AI della chat';
COMMENT ON COLUMN message_feedbacks.message_id IS 'Messaggio AI valutato';
COMMENT ON COLUMN message_feedbacks.user_id IS 'Utente che ha inviato il feedback';
COMMENT ON COLUMN message_feedbacks.is_positive IS 'TRUE=feedback positivo, FALSE=negativo';
COMMENT ON COLUMN message_feedbacks.reason_category IS 'Categoria motivo per feedback negativo';
COMMENT ON COLUMN message_feedbacks.comment IS 'Commento libero opzionale';
