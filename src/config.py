"""Runtime configuration models for scanner, governance, LLM provider, and S3A bridge."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class UserProfileConfig(BaseModel):
    author_names: List[str] = Field(default_factory=list)
    orcids: List[str] = Field(default_factory=list)
    institutions: List[str] = Field(default_factory=list)
    collaborators: List[str] = Field(default_factory=list)


class LLMConfig(BaseModel):
    provider: str = "openai"
    model_name: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    max_tokens: int = 2048
    allow_remote: bool = False


class ScannerConfig(BaseModel):
    workspace_root: str = "."
    metadata_dir: str = ".s3a/metadata"
    staging_dir: str = ".s3a/staging"
    audit_log_path: str = ".s3a/audit_log.jsonl"
    confidence_threshold: float = 0.85
    debounce_sec: int = 30


class S3AConfig(BaseModel):
    harness_endpoint: str = "http://localhost:9090"
    addon_channel: str = "gate://s3a_edu"
    lrs_endpoint: str = "http://localhost:8080/xapi"
    s3a_database_path: str = "research_vault.s3a"
    scholar_layout_version: int = 1


class AppConfig(BaseModel):
    user_profile: UserProfileConfig = Field(default_factory=UserProfileConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    scanner: ScannerConfig = Field(default_factory=ScannerConfig)
    s3a: S3AConfig = Field(default_factory=S3AConfig)

    @classmethod
    def load(cls, config_path: Optional[str | Path] = None) -> AppConfig:
        if config_path:
            p = Path(config_path)
            if p.is_file():
                return cls.model_validate_json(p.read_text(encoding="utf-8"))
        default_path = Path(".s3a/config.json")
        if default_path.is_file():
            return cls.model_validate_json(default_path.read_text(encoding="utf-8"))
        return cls()
