ALTER TABLE webhook_logs ADD COLUMN chat_type TEXT;
ALTER TABLE webhook_logs ADD COLUMN message_id INTEGER;
ALTER TABLE webhook_logs ADD COLUMN command TEXT;
ALTER TABLE webhook_logs ADD COLUMN text TEXT;
