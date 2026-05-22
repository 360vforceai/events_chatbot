from supabase import create_client, Client
from app.config import settings
_supabase: Client = None
def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not settings.supabase_url or not settings.supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are not configured")
        _supabase = create_client(settings.supabase_url, settings.supabase_key)
    return _supabase