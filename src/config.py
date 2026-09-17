"""
LexIndia Configuration Module
Defines model roles, provider bindings, database paths, and feature flags.
Never hardcodes secrets or provider strings.
"""

from typing import Optional, Literal
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import logging

# Set up base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider Configuration
    LLM_PROVIDER: Literal["groq", "together", "hf"] = Field(
        default="groq",
        description="LLM Provider to use (groq | together | hf)"
    )
    GROQ_API_KEY: Optional[str] = Field(default=None, description="API Key for Groq Cloud")
    GROQ_BASE_URL: str = Field(default="https://api.groq.com/openai/v1", description="Groq API base URL")

    TOGETHER_API_KEY: Optional[str] = Field(default=None, description="API Key for Together AI")
    TOGETHER_BASE_URL: str = Field(default="https://api.together.xyz/v1", description="Together API base URL")

    HF_TOKEN: Optional[str] = Field(default=None, description="Hugging Face API Token")
    HF_BASE_URL: str = Field(default="https://api-inference.huggingface.co/v1", description="Hugging Face Inference base URL")

    # Model Roles (Role-based configuration as mandated by SPEC)
    GENERATION_MODEL: str = Field(
        default="openai/gpt-oss-120b",
        description="Primary Generation LLM role (e.g. openai/gpt-oss-120b or llama-3.3-70b-versatile)"
    )
    EXPANSION_MODEL: str = Field(
        default="qwen/qwen3.8-27b",
        description="Query Expansion LLM role"
    )

    # Fallback & Evaluation Models
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API Key")
    JUDGE_PRIMARY: str = Field(default="gemini-2.5-flash", description="Primary cross-model evaluation judge")

    @property
    def JUDGE_SECONDARY(self) -> str:
        """Secondary judge defaults to the value of GENERATION_MODEL."""
        return self.GENERATION_MODEL

    # Search & Vector Indexing
    ES_URL: str = Field(default="http://localhost:9200", description="Elasticsearch cluster URL")
    ES_INDEX: str = Field(default="lexindia_corpus", description="Elasticsearch corpus index name")
    EMBEDDING_MODEL_NAME: str = Field(default="BAAI/bge-base-en-v1.5", description="Local dense vector model")
    RERANKER_MODEL_NAME: str = Field(default="BAAI/bge-reranker-base", description="Local cross-encoder reranker")

    # Storage Paths
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = BASE_DIR / "data" / "raw"
    PROCESSED_DATA_DIR: Path = BASE_DIR / "data" / "processed"
    EVAL_DATA_DIR: Path = BASE_DIR / "data" / "eval"
    REVIEWS_DB_PATH: Path = BASE_DIR / "data" / "reviews.db"
    CHECKPOINTS_DB_PATH: Path = BASE_DIR / "data" / "checkpoints.db"

    # Feature Flags & System Options
    ENABLE_GST: bool = Field(default=False, description="Enable secondary GST corpus indexing & retrieval")
    ENABLE_LANGFUSE: bool = Field(default=False, description="Enable Langfuse observability tracing")
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # API Settings
    FASTAPI_HOST: str = "0.0.0.0"
    FASTAPI_PORT: int = 8000
    RATE_LIMIT_PER_MINUTE: int = 30


# Singleton settings instance
settings = Settings()

# Structured Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("lexindia")
