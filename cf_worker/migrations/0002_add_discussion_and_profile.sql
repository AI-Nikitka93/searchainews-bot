ALTER TABLE items ADD COLUMN discussion_context TEXT;
ALTER TABLE items ADD COLUMN content_profile TEXT;
CREATE INDEX IF NOT EXISTS idx_items_content_profile ON items(content_profile);
