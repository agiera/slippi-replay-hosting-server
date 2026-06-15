from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "fastapi-react-auth-boilerplate"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@db:5432/app"
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    CORS_ORIGINS: str = "http://localhost:5173"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    FRONTEND_URL: str = "http://localhost:5173"

    SUPERUSER_USERNAME: str = ""
    SUPERUSER_EMAIL: str = ""
    SUPERUSER_PASSWORD: str = ""
    REPLAY_STORAGE_DIR: str = "/app/uploads"
    FTP_ENABLED: bool = False
    FTP_HOST: str = "0.0.0.0"
    FTP_PORT: int = 2121
    FTP_PASSIVE_PORTS: str = ""
    FTP_STAGING_DIR: str = "/tmp/slippi-ftp-staging"
    FTP_MAX_CONNECTIONS: int = 128
    FTP_MAX_CONNECTIONS_PER_IP: int = 8

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
