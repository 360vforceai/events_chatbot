from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    discord_bot_token: str
    discord_guild_id: str
    openai_api_key: str
    admin_api_key: str
    supabase_url: str | None = None
    supabase_key: str | None = None
    scrape_interval_hours: int = 6

    # Legacy — unused by Supabase-backed code; kept for backward-compatible .env files
    aws_access_key_id: str = "local"
    aws_secret_access_key: str = "local"
    aws_region: str = "us-east-1"
    dynamodb_table_clubs: str = "seer-clubs"
    dynamodb_table_events: str = "seer-events"
    dynamodb_table_users: str = "seer-users"
    dynamodb_table_interactions: str = "seer-interactions"

    @field_validator(
        "discord_bot_token",
        "discord_guild_id",
        "openai_api_key",
        "admin_api_key",
        "supabase_url",
        "supabase_key",
        mode="before",
    )
    @classmethod
    def strip_whitespace(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


settings = Settings()
