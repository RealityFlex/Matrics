-- Миграция для добавления полей QR кода и связи с группами в таблицу events

-- Добавить колонки для QR кода, если их нет
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='events' AND column_name='qr_token') THEN
        ALTER TABLE events ADD COLUMN qr_token VARCHAR(100);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='events' AND column_name='qr_token_generated_at') THEN
        ALTER TABLE events ADD COLUMN qr_token_generated_at TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- Создать таблицу event_groups, если её нет
CREATE TABLE IF NOT EXISTS event_groups (
    event_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    PRIMARY KEY (event_id, group_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES student_groups(id) ON DELETE CASCADE
);

