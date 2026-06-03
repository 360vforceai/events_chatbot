-- SEER Initial Schema
-- Run this in Supabase Dashboard → SQL Editor

CREATE TABLE IF NOT EXISTS public.clubs (
    club_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    category    TEXT[],
    campus      TEXT,
    meeting_time TEXT,
    links       JSONB,
    tags        TEXT[],
    last_updated TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.events (
    event_id    TEXT PRIMARY KEY,
    club_id     TEXT,
    title       TEXT NOT NULL,
    date        DATE,
    time        TEXT,
    location    TEXT,
    campus      TEXT,
    type        TEXT,
    description TEXT,
    free_food   BOOLEAN DEFAULT FALSE,
    rsvp_link   TEXT
);

CREATE TABLE IF NOT EXISTS public.interactions (
    interaction_id UUID PRIMARY KEY,
    user_id        TEXT NOT NULL,
    username       TEXT,
    query          TEXT,
    response       TEXT,
    timestamp      BIGINT
);

-- Indexes for fast search
CREATE INDEX IF NOT EXISTS idx_clubs_name        ON public.clubs (name);
CREATE INDEX IF NOT EXISTS idx_events_date       ON public.events (date);
CREATE INDEX IF NOT EXISTS idx_interactions_user ON public.interactions (user_id, timestamp DESC);
