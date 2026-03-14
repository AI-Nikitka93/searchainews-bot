ALTER TABLE users ADD COLUMN language TEXT NOT NULL DEFAULT 'ru';
UPDATE users SET language = 'ru' WHERE language IS NULL;
