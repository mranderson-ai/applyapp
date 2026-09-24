"""Runtime settings loaded from the project `.env` (never from chat context).

`PROJECT_ROOT` is two levels above this file (`src/applyapp/config.py` → repo root)
so `.env`, `credentials.json`, and `token.json` resolve the same way whether you
run from Cursor, a LaunchAgent, or a future desktop wrapper.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All knobs the unattended worker needs. Extra env vars are ignored."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    # Sonnet 5 is the quality/cost default for several structured calls per job.
    anthropic_model: str = "claude-sonnet-5"
    # OpenAI-compatible hosts (OpenAI, OpenRouter, Groq, Ollama, vLLM) use this key
    # when a step's provider is `openai` and that step has no key of its own.
    openai_api_key: str = ""

    # Defaults for every LLM step. Blank model/key inherit the Anthropic fields above
    # so an existing `.env` keeps working. Per-step vars override these.
    llm_provider: str = "anthropic"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""

    analyze_provider: str = ""
    analyze_model: str = ""
    analyze_api_key: str = ""
    analyze_base_url: str = ""

    resume_provider: str = ""
    resume_model: str = ""
    resume_api_key: str = ""
    resume_base_url: str = ""

    cover_provider: str = ""
    cover_model: str = ""
    cover_api_key: str = ""
    cover_base_url: str = ""

    format_provider: str = ""
    format_model: str = ""
    format_api_key: str = ""
    format_base_url: str = ""

    critique_provider: str = ""
    critique_model: str = ""
    critique_api_key: str = ""
    critique_base_url: str = ""

    google_sheet_id: str = ""
    # `google` is the Sheet. `local` is jobs.xlsx with the same headers.
    job_queue: str = "google"
    local_jobs_path: str = ""
    google_seed_folder_id: str = ""
    google_output_folder_id: str = ""
    # `google` reads and writes Drive Docs. `local` reads LOCAL_SEED_DIR and writes formatted .docx files.
    document_store: str = "google"
    local_seed_dir: str = ""
    local_output_dir: str = ""
    google_credentials_path: Path = Field(default=PROJECT_ROOT / "credentials.json")
    google_token_path: Path = Field(default=PROJECT_ROOT / "token.json")

    # Critique may send the writer back around this many times, then we format anyway.
    max_revisions: int = 2
    max_posting_chars: int = 50_000
    # Seed budget is shared across facts, ATS paper, design spec, voice, and resumes.
    max_seed_chars: int = 150_000


def get_settings() -> Settings:
    return Settings()
