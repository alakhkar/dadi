-- Run this in your Supabase SQL editor

CREATE TABLE IF NOT EXISTS user_memories (
    id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id    text        NOT NULL,
    memory     text        NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_memories_user_id_idx ON user_memories (user_id);
