ALTER TABLE items ADD COLUMN source_id TEXT;
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_id);
