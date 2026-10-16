"""Centralized Configuration - Environment Variables

Single place where the project reads its configuration:

- ``Settings`` holds OUR settings (model, endpoint, temperature, ...). Each field
  maps to the environment variable of the same name, case-insensitively
  (``ollama_model`` <- ``OLLAMA_MODEL``), read from the real environment or `.env`.
- ``load_dotenv()`` runs once, when this module is imported, so third-party SDKs
  that read ``os.environ`` directly (LangSmith, Langfuse, Pinecone, Hugging Face)
  see the same `.env`. Other modules should not call it again.
"""

import logging

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Export `.env` to os.environ for the SDKs above. Variables already set in the
# real environment are never overridden.
load_dotenv()


class Settings(BaseSettings):
    """Loads configuration from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ollama_model: str = Field(default="mistral")
    ollama_base_url: str = Field(default="http://localhost:11434/v1")
    openai_api_key: str = Field(default="ollama")
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=512, ge=1, le=4096)
    chroma_path: str = Field(default="./data/chroma")
    pinecone_api_key: str | None = Field(default=None)
    hf_token: str | None = Field(default=None)
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")


_settings: Settings | None = None


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
