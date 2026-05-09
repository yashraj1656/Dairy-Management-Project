from pydantic_settings import BaseSettings

from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "Dairy Management API"
    DATABASE_URL: str = "sqlite:///./dairydb.sqlite3"
    SECRET_KEY: str = "a_super_secret_key_for_jwt_auth_in_production_change_this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    CORS_ORIGINS: List[str] = ["http://127.0.0.1:3000", "http://localhost:3000", "https://your-frontend-domain.com"]

    class Config:
        env_file = ".env"

settings = Settings()
