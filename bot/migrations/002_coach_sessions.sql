-- Coach sessions: persistent multi-turn agent memory
-- Run in Supabase Dashboard → SQL Editor

CREATE TABLE IF NOT EXISTS public.coach_sessions (
    session_id   UUID PRIMARY KEY,
    user_id      TEXT NOT NULL,
    username     TEXT,
    goal         TEXT NOT NULL,
    domain       TEXT NOT NULL DEFAULT 'general',
    thread_id    BIGINT,
    channel_id   BIGINT,
    status       TEXT NOT NULL DEFAULT 'active',
    ended_reason TEXT,
    turn_count   INT NOT NULL DEFAULT 0,
    messages     JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at   BIGINT NOT NULL,
    updated_at   BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_coach_sessions_user_active
    ON public.coach_sessions (user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_coach_sessions_thread
    ON public.coach_sessions (thread_id)
    WHERE thread_id IS NOT NULL;
