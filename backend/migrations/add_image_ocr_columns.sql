-- ============================================================================
-- Migration: Add image_data and ocr_text columns to chat_messages
-- Run: psql -h localhost -U postgres -d smartorder -f migrations/add_image_ocr_columns.sql
-- ============================================================================

ALTER TABLE chat_messages
ADD COLUMN IF NOT EXISTS image_data BYTEA;

ALTER TABLE chat_messages
ADD COLUMN IF NOT EXISTS ocr_text TEXT;

-- Comments for documentation
COMMENT ON COLUMN chat_messages.image_data IS 'Base64-encoded image data (JPEG/PNG/WebP) uploaded by user for OCR';
COMMENT ON COLUMN chat_messages.ocr_text IS 'OCR text extracted by GPT-4o Vision. NULL for text messages.';
