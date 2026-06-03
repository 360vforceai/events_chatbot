-- Add club_name column to events for searchable org association
ALTER TABLE public.events ADD COLUMN IF NOT EXISTS club_name TEXT;

-- Index for fast club name search
CREATE INDEX IF NOT EXISTS idx_events_club_name ON public.events (club_name);
