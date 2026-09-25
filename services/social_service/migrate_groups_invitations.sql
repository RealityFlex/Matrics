-- Миграция для добавления поля creator_id в таблицу student_groups и создания таблицы group_invitations

-- Добавить колонку creator_id в таблицу student_groups, если её нет
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='student_groups' AND column_name='creator_id') THEN
        ALTER TABLE student_groups ADD COLUMN creator_id INTEGER;
        
        -- Создать индекс для creator_id
        CREATE INDEX IF NOT EXISTS ix_student_groups_creator_id ON student_groups(creator_id);
        
        -- Добавить внешний ключ
        ALTER TABLE student_groups 
        ADD CONSTRAINT fk_student_groups_creator_id 
        FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE SET NULL;
        
        -- Установить creator_id для существующих групп на первого участника (если есть)
        UPDATE student_groups sg
        SET creator_id = (
            SELECT gm.user_id 
            FROM group_members gm 
            WHERE gm.group_id = sg.id 
            ORDER BY gm.joined_at ASC 
            LIMIT 1
        )
        WHERE creator_id IS NULL 
        AND EXISTS (SELECT 1 FROM group_members WHERE group_id = sg.id);
    END IF;
END $$;

-- Создать таблицу group_invitations, если её нет
CREATE TABLE IF NOT EXISTS group_invitations (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    inviter_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    responded_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (group_id) REFERENCES student_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (inviter_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_group_invitations_status CHECK (status IN ('pending', 'accepted', 'rejected'))
);

-- Создать индексы для group_invitations
CREATE INDEX IF NOT EXISTS ix_group_invitations_group_id ON group_invitations(group_id);
CREATE INDEX IF NOT EXISTS ix_group_invitations_user_id ON group_invitations(user_id);
CREATE INDEX IF NOT EXISTS ix_group_invitations_inviter_id ON group_invitations(inviter_id);
CREATE INDEX IF NOT EXISTS ix_group_invitations_status ON group_invitations(status);

