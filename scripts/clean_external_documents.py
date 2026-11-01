"""Remove stale external cache/vector entries that fail the current subject check."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

# Running `python scripts/clean_external_documents.py` makes scripts/ the
# import root, so add the project root explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chromadb

from src.config import get_settings
from src.data_loader import item_lookup, load_items
from src.indexer import EXTERNAL_COLLECTION
from src.models import ExternalDocument
from src.relevance import external_title_matches_item


def main() -> None:
    settings = get_settings()
    items, _ = load_items(settings.data_dir)
    items_by_id = item_lookup(items)
    cache_removed = 0

    for cache_path in settings.cache_dir.glob("wiki_*.json"):
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            raw_documents = payload if isinstance(payload, list) else payload.get("documents", [])
            documents = [ExternalDocument(**document) for document in raw_documents]
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        valid = [doc for doc in documents if doc.related_item_id in items_by_id and external_title_matches_item(items_by_id[doc.related_item_id], doc.title)]
        if len(valid) == len(documents):
            continue
        cache_removed += len(documents) - len(valid)
        audit = {} if isinstance(payload, list) else dict(payload.get("audit", {}))
        rejected = [doc.title for doc in documents if doc not in valid]
        audit["selected"] = [doc.title for doc in valid]
        audit["discarded"] = list(dict.fromkeys([*audit.get("discarded", []), *rejected]))
        audit["rejected_as_unrelated"] = rejected
        cache_path.write_text(json.dumps({"documents": [asdict(doc) for doc in valid], "audit": audit}, ensure_ascii=False, indent=2), encoding="utf-8")

    vector_removed = 0
    if settings.chroma_dir.exists():
        client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        try:
            collection = client.get_collection(EXTERNAL_COLLECTION)
            stored = collection.get(include=["metadatas"])
            invalid_ids = [
                chunk_id
                for chunk_id, metadata in zip(stored.get("ids", []), stored.get("metadatas", []))
                if metadata
                and metadata.get("related_item_id") in items_by_id
                and not external_title_matches_item(items_by_id[metadata["related_item_id"]], metadata.get("document_title", ""))
            ]
            if invalid_ids:
                collection.delete(ids=invalid_ids)
                vector_removed = len(invalid_ids)
        except Exception as exc:
            print(f"벡터 저장소 정리를 건너뜁니다: {exc}")

    print(f"캐시에서 부적합 문서 {cache_removed}개, 벡터 저장소에서 청크 {vector_removed}개를 제거했습니다.")


if __name__ == "__main__":
    main()
