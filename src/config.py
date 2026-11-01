from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    chroma_dir: Path
    cache_dir: Path
    chat_model: str
    embedding_model: str
    wiki_contact: str
    chunk_size: int
    chunk_overlap: int
    retrieval_top_k: int
    wiki_requests_per_minute: int

    @property
    def api_key(self) -> str:
        """Use the project-provided GMS key, with a standard OpenAI key as fallback."""
        return os.getenv("GMS_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()

    @property
    def uses_gms_key(self) -> bool:
        return bool(os.getenv("GMS_KEY", "").strip())

    @property
    def api_base_url(self) -> str | None:
        """Return the OpenAI-compatible gateway URL for the active key, when configured."""
        if self.uses_gms_key:
            return os.getenv("GMS_BASE_URL", "https://gms.ssafy.io/gmsapi/api.openai.com/v1/").strip() or None
        return os.getenv("OPENAI_BASE_URL", "").strip() or None

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)


def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        project_root=PROJECT_ROOT,
        data_dir=PROJECT_ROOT / "EPL_2000-2026_json",
        chroma_dir=PROJECT_ROOT / "storage" / "chroma",
        cache_dir=PROJECT_ROOT / "storage" / "cache",
        chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-5.4-nano"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        wiki_contact=os.getenv("WIKI_CONTACT", "").strip(),
        chunk_size=_int_env("CHUNK_SIZE", 1000),
        chunk_overlap=_int_env("CHUNK_OVERLAP", 200),
        retrieval_top_k=_int_env("RETRIEVAL_TOP_K", 5),
        wiki_requests_per_minute=_int_env("WIKI_REQUESTS_PER_MINUTE", 10),
    )
