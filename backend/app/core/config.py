from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "教师综合成果与职称材料管理平台"
    secret_key: str = "development-only-change-this-secret"
    bootstrap_admin_password: str = ""
    database_url: str = "sqlite:///./data/teacher_platform.db"
    storage_root: Path = Path("./storage")
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    cors_origins: str = "http://localhost:5173"
    access_token_minutes: int = 720
    max_upload_mb: int = 50
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
