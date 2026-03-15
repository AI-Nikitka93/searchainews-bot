CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at);
CREATE INDEX IF NOT EXISTS idx_items_score_date ON items(impact_score, published_at, created_at);
CREATE INDEX IF NOT EXISTS idx_users_subscribed ON users(is_subscribed);
