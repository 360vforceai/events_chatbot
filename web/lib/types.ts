export interface Club {
  club_id: string;
  name: string;
  description: string;
  category: string[];
  campus: string;
  meeting_time?: string;
  links: { instagram?: string; website?: string; getinvolved?: string };
  tags: string[];
  last_updated?: string;
}

export interface Event {
  event_id: string;
  club_id: string;
  title: string;
  date: string;
  time: string;
  location: string;
  campus: string;
  type: string;
  description?: string;
  free_food: boolean;
  rsvp_link?: string;
}

export interface UserPreferences {
  discord_user_id: string;
  major?: string;
  interests: string[];
  preferred_campus?: string;
  subscriptions: string[];
  digest_enabled: boolean;
}

export interface Recommendation {
  club_id: string;
  match_score: number;
  reason: string;
  club?: Club;
}
