-- ============================================================================
-- Migration: Add export_folder column to app_users
-- Run: psql -h localhost -U postgres -d smartorder -f migrations/add_export_folder.sql
-- ============================================================================

ALTER TABLE app_users
ADD COLUMN IF NOT EXISTS export_folder VARCHAR(500);

-- Comment per documentazione
COMMENT ON COLUMN app_users.export_folder IS 'Cartella di esportazione ordini configurata dall''operatore (path assoluto)';
