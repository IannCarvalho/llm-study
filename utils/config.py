"""Centralized Configuration - Environment Variables"""

import logging
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application configuration."""

    ollama_model: str = Field(default="mistral", env="OLLAMA_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434/v1", env="OLLAMA_BASE_URL")
    openai_api_key: str = Field(default="ollama", env="OPENAI_API_KEY")
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=512, ge=1, le=4096, env="LLM_MAX_TOKENS")
    chroma_path: str = Field(default="./data/chroma", env="CHROMA_PATH")
    pinecone_api_key: Optional[str] = Field(default=None, env="PINECONE_API_KEY")
    hf_token: Optional[str] = Field(default=None, env="HF_TOKEN")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
        logger.debug(f"Settings initialized with model={_settings.ollama_model}")
    return _settings


def get_config() -> Settings:
    """Alias for get_settings()."""
    return get_settings()


__all__ = ["Settings", "get_settings", "get_config"]
