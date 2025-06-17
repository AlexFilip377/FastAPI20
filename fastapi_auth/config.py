from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:1234@db:5432/postgres"
    SECRET_KEY: str = "defaultsecret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REDIS_URL: str = "redis://localhost:6379/0"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
@lru_cache
def get_settings():
    return Settings()

RATE_LIMIT = {
    "limit": 5,
    "window": 60,
}