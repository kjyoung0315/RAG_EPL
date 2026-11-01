from __future__ import annotations

from langchain_core.documents import Document

from src.config import Settings
from src.indexer import EXTERNAL_COLLECTION, get_store
from src.models import EPLItem, Evidence
from src.relevance import metadata_title_matches_item


class EPLRetriever:
    def __init__(self, settings: Settings, catalog: list[EPLItem] | None = None) -> None:
        self.external_store = get_store(settings, EXTERNAL_COLLECTION)
        self.top_k = settings.retrieval_top_k
        self.team_squads = {
            str(entry.metadata.get("team")): entry
            for entry in catalog or []
            if entry.item_type == "team_squad_current"
        }

    def retrieve(self, item: EPLItem, question: str) -> list[Evidence]:
        """Prefer Wikipedia API documents; retain the bundled record as a fallback."""
        evidence: list[Evidence] = []
        documents = self.external_store.similarity_search(question, k=self.top_k, filter={"related_item_id": item.item_id})
        seen: set[str] = set()
        for document in documents:
            # Existing persistent indexes may predate candidate validation. Never
            # expose a document whose title is about another player.
            if not metadata_title_matches_item(item, document.metadata):
                continue
            fingerprint = self._fingerprint(document.page_content, str(document.metadata.get("source_url", "")))
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            evidence.append(
                Evidence(
                    label=len(evidence) + 1,
                    text=document.page_content,
                    title=str(document.metadata.get("document_title", "외부 문서")),
                    source_url=str(document.metadata.get("source_url", "")),
                    source_type=str(document.metadata.get("source_type", "external")),
                    item_id=item.item_id,
                )
            )
        squad = self.team_squads.get(str(item.metadata.get("team") or item.title)) if item.item_type == "team_current" else None
        if squad:
            squad_fingerprint = self._fingerprint(squad.text, str(squad.metadata.get("source_url", "")))
            if squad_fingerprint not in seen:
                seen.add(squad_fingerprint)
                evidence.append(
                    Evidence(
                        label=len(evidence) + 1,
                        text=squad.text,
                        title=squad.title,
                        source_url=str(squad.metadata.get("source_url", "")),
                        source_type="EPL 로컬 JSON (현재 선수단)",
                        item_id=squad.item_id,
                    )
                )
        local_fingerprint = self._fingerprint(item.text, str(item.metadata.get("source_url", "")))
        if local_fingerprint not in seen:
            evidence.append(
                Evidence(
                    label=len(evidence) + 1,
                    text=item.text,
                    title=item.title,
                    source_url=str(item.metadata.get("source_url", "")),
                    source_type="EPL 로컬 JSON (보완 근거)",
                    item_id=item.item_id,
                )
            )
        return evidence

    @staticmethod
    def _fingerprint(text: str, source_url: str) -> str:
        return f"{source_url}|{text[:180].strip()}"
