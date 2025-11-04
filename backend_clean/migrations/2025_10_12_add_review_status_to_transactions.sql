-- Add review status tracking columns for bank movements
ALTER TABLE bank_movements
    ADD COLUMN IF NOT EXISTS review_status TEXT DEFAULT 'pending';

ALTER TABLE bank_movements
    ADD COLUMN IF NOT EXISTS reviewed_by INTEGER REFERENCES users(id);

ALTER TABLE bank_movements
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP;
