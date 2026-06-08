from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    minimax_api_key: str = Field(default="", alias="MINIMAX_API_KEY")
    minimax_base_url: str = Field(default="https://api.minimaxi.com/v1", alias="MINIMAX_BASE_URL")
    minimax_model: str = Field(default="MiniMax-M3", alias="MINIMAX_MODEL")
    minimax_max_base64_mb: int = Field(default=45, alias="MINIMAX_MAX_BASE64_MB")
    minimax_enable_files_api: bool = Field(default=False, alias="MINIMAX_ENABLE_FILES_API")
    minimax_file_purpose: str = Field(default="vision", alias="MINIMAX_FILE_PURPOSE")
    max_upload_mb: int = Field(default=500, alias="MAX_UPLOAD_MB")
    upload_dir: Path = Field(default=Path("./storage/uploads"), alias="UPLOAD_DIR")
    result_dir: Path = Field(default=Path("./storage/results"), alias="RESULT_DIR")
    allowed_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="ALLOWED_ORIGINS",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.result_dir.mkdir(parents=True, exist_ok=True)
    return settings
