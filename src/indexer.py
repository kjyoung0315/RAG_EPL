from __future__ import annotations

import json
from collections.abc import Iterable

import chromadb
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from src.config import Settings
from src.data_loader import LoadReport, load_items
from src.models import EPLItem


ITEM_COLLECTION = "epl_items"
EXTERNAL_COLLECTION = "epl_external_docs"
# Bump this whenever normalized local document text/metadata changes.  It makes
# an existing persistent store refresh itself once instead of silently serving
# stale documents after an application update.
ITEM_INDEX_SCHEMA_VERSION = "2026-10-22-team-squad-snapshots-v1"


def embeddings(settings: Settings) -> OpenAIEmbeddings:
    if not settings.has_api_key:
        raise RuntimeError("GMS_KEY is missing. Add it to .env before indexing.")
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.api_key,
        base_url=settings.api_base_url,
    )


def get_store(settings: Settings, collection_name: str) -> Chroma:
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=collection_name,
        persist_directory=str(settings.chroma_dir),
        embedding_function=embeddings(settings),
    )


def collection_count(settings: Settings, collection_name: str) -> int:
    """Read a persisted Chroma collection count without requiring an embedding/API client."""
    if not settings.chroma_dir.exists():
        return 0
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    try:
        return client.get_collection(collection_name).count()
    except Exception:  # Chroma raises a version-specific not-found error.
        return 0


def _item_index_state_path(settings: Settings):
    return settings.chroma_dir.parent / "item_index_state.json"


def is_item_index_current(settings: Settings, expected_count: int) -> bool:
    """Whether the persisted local index matches the current document schema."""
    if collection_count(settings, ITEM_COLLECTION) < expected_count:
        return False
    try:
        state = json.loads(_item_index_state_path(settings).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return state == {"schema_version": ITEM_INDEX_SCHEMA_VERSION, "item_count": expected_count}


def index_items(settings: Settings, batch_size: int = 64) -> tuple[LoadReport, int]:
    items, report = load_items(settings.data_dir)
    store = get_store(settings, ITEM_COLLECTION)
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        store.add_texts(
            texts=[item.text for item in batch],
            metadatas=[item.chroma_metadata() for item in batch],
            ids=[item.item_id for item in batch],
        )
    count = store._collection.count()
    _item_index_state_path(settings).write_text(
        json.dumps({"schema_version": ITEM_INDEX_SCHEMA_VERSION, "item_count": len(items)}, ensure_ascii=False),
        encoding="utf-8",
    )
    return report, count


def index_external_chunks(
    settings: Settings,
    texts: Iterable[str],
    metadatas: Iterable[dict[str, str | int | float | bool]],
    ids: Iterable[str],
) -> int:
    store = get_store(settings, EXTERNAL_COLLECTION)
    store.add_texts(list(texts), metadatas=list(metadatas), ids=list(ids))
    return store._collection.count()
