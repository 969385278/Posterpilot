from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from app.core.paths import PROJECT_ROOT, project_path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="POSTERPILOT_",
        extra="ignore",
    )

    app_name: str = "PosterPilot API"
    environment: str = Field(default="development", validation_alias="POSTERPILOT_ENV")
    api_host: str = "127.0.0.1"
    api_port: int = 8787
    log_level: str = "INFO"
    data_dir: Path = Path("data")
    database_url: str = "sqlite:///data/posterpilot.sqlite3"
    langgraph_checkpoint_path: Path = Field(
        default=Path("data/langgraph-checkpoints.sqlite3"),
        validation_alias="LANGGRAPH_CHECKPOINT_PATH",
    )
    chroma_url: str = Field(
        default="http://127.0.0.1:8000",
        validation_alias="CHROMA_URL",
    )
    rag_collection_name: str = Field(
        default="posterpilot_design_knowledge",
        validation_alias="RAG_COLLECTION_NAME",
    )
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias="OLLAMA_BASE_URL",
    )
    ollama_embedding_model: str = Field(
        default="bge-m3",
        validation_alias="OLLAMA_EMBEDDING_MODEL",
    )
    embedding_timeout_seconds: float = Field(
        default=120,
        validation_alias="EMBEDDING_TIMEOUT_SECONDS",
        gt=0,
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias="DEEPSEEK_BASE_URL",
    )
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    deepseek_text_model: str = Field(
        default="deepseek-v4-flash",
        validation_alias="DEEPSEEK_TEXT_MODEL",
    )
    text_model_timeout_seconds: float = Field(
        default=60,
        validation_alias="TEXT_MODEL_TIMEOUT_SECONDS",
        gt=0,
    )
    ark_base_url: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3",
        validation_alias="ARK_BASE_URL",
    )
    ark_api_key: str = Field(default="", validation_alias="ARK_API_KEY")
    ark_image_model: str = Field(
        default="doubao-seedream-4-5-251128",
        validation_alias="ARK_IMAGE_MODEL",
    )
    ark_image_size: str = Field(default="2K", validation_alias="ARK_IMAGE_SIZE")
    ark_image_response_format: str = Field(
        default="url",
        validation_alias="ARK_IMAGE_RESPONSE_FORMAT",
    )
    ark_image_output_format: str = Field(
        default="jpeg",
        validation_alias="ARK_IMAGE_OUTPUT_FORMAT",
    )
    ark_vision_model: str = Field(default="", validation_alias="ARK_VISION_MODEL")
    image_model_timeout_seconds: float = Field(
        default=90,
        validation_alias="IMAGE_MODEL_TIMEOUT_SECONDS",
        gt=0,
    )
    vision_model_timeout_seconds: float = Field(
        default=60,
        validation_alias="VISION_MODEL_TIMEOUT_SECONDS",
        gt=0,
    )
    comfyui_base_url: str = Field(
        default="http://127.0.0.1:8188",
        validation_alias="COMFYUI_BASE_URL",
    )
    comfyui_workflow_path: str = Field(default="", validation_alias="COMFYUI_WORKFLOW_PATH")
    comfyui_prompt_node_id: str = Field(default="", validation_alias="COMFYUI_PROMPT_NODE_ID")
    comfyui_prompt_input: str = Field(default="text", validation_alias="COMFYUI_PROMPT_INPUT")
    comfyui_timeout_seconds: float = Field(
        default=90,
        validation_alias="COMFYUI_TIMEOUT_SECONDS",
        gt=0,
    )
    deepgaze_base_url: str = Field(
        default="http://127.0.0.1:8001",
        validation_alias="DEEPGAZE_BASE_URL",
    )
    deepgaze_timeout_seconds: float = Field(
        default=60,
        validation_alias="DEEPGAZE_TIMEOUT_SECONDS",
        gt=0,
    )

    @field_validator("data_dir", "langgraph_checkpoint_path", mode="after")
    @classmethod
    def resolve_storage_path(cls, value: Path) -> Path:
        return project_path(value)

    @field_validator("database_url", mode="after")
    @classmethod
    def resolve_database_path(cls, value: str) -> str:
        url = make_url(value)
        if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
            return value
        # SQLite file: URIs have their own path/query semantics; never rewrite them.
        if url.query.get("uri") == "true":
            return value
        return url.set(database=project_path(url.database).as_posix()).render_as_string(
            hide_password=False
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
