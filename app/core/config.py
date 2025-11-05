from dotenv import load_dotenv

load_dotenv()

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ADMIN_EMAIL: str
    ADMIN_PASS: str
    APP_MODULE: str
    HOST: str
    PORT: int
    MAX_PROFILES_PER_USER: int = 2 
settings = Settings()
