from supabase import create_client, Client
from app.config import settings
_supabase: Client = None
def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.supabase_url, settings.supabase_key)
    return _supabase