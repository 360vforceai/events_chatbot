from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    discord_bot_token: str
    discord_guild_id: str
    openai_api_key: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    dynamodb_table_clubs: str = "seer-clubs"
    dynamodb_table_events: str = "seer-events"
    dynamodb_table_users: str = "seer-users"
    dynamodb_table_interactions: str = "seer-interactions"
    scrape_interval_hours: int = 6
    admin_api_key: str

    class Config:
        env_file = ".env"


settings = Settings()
