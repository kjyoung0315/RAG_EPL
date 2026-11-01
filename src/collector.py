from __future__ import annotations

import hashlib
import html
import json
import re
import time
from urllib.parse import quote, unquote, urlparse
from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import Settings
from src.indexer import index_external_chunks
from src.llm import LLMService
from src.models import EPLItem, ExternalDocument, ProfileImage, compact_metadata
from src.relevance import PLAYER_ITEM_TYPES, TEAM_ITEM_TYPES, external_title_matches_item


WIKI_API_URL = "https://ko.wikipedia.org/w/api.php"


class WikipediaCollector:
    def __init__(self, settings: Settings, llm: LLMService) -> None:
        self.settings = settings
        self.llm = llm
        self.session = requests.Session()
        contact = settings.wiki_contact or "contact-not-configured"
        self.session.headers.update({"User-Agent": f"EPLInsightRAG/1.0 ({contact})"})
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request_at = 0.0
        self.last_audits: list[dict[str, Any]] = []
        self.last_question_cache_hit = False

    def _wait_for_rate_limit(self) -> None:
        interval = 60 / max(self.settings.wiki_requests_per_minute, 1)
        remaining = interval - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_at = time.monotonic()

    def _request(self, params: dict[str, str], api_url: str = WIKI_API_URL) -> dict[str, Any]:
        self._wait_for_rate_limit()
        response = self.session.get(api_url, params={"format": "json", "utf8": "1", **params}, timeout=15)
        response.raise_for_status()
        return response.json()

    def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        payload = self._request({"action": "query", "list": "search", "srsearch": query, "srlimit": str(limit)})
        candidates: list[dict[str, str]] = []
        for entry in payload.get("query", {}).get("search", []):
            title = str(entry["title"])
            candidates.append({"title": title, "snippet": re_strip_html(str(entry.get("snippet", "")))})
        return candidates

    def fetch_extract(self, title: str) -> tuple[str, str]:
        payload = self._request(
            {"action": "query", "prop": "extracts|info", "exintro": "0", "explaintext": "1", "inprop": "url", "titles": title}
        )
        pages = payload.get("query", {}).get("pages", {})
        page = next(iter(pages.values()), {})
        return str(page.get("extract", "")).strip(), str(page.get("fullurl", ""))

    def _cache_path(self, item_id: str, query: str) -> Path:
        digest = hashlib.sha256(f"{item_id}:{query}".encode()).hexdigest()[:16]
        return self.settings.cache_dir / f"wiki_{digest}.json"

    def _question_cache_path(self, item_id: str, question: str) -> Path:
        """Store extracted search terms per item and original user question.

        The query cache below already prevents repeat Wikipedia requests.  This
        additional cache keeps the LLM from producing a slightly different set
        of search terms on a repeated question, which could otherwise bypass
        that cache and trigger a new external collection.
        """
        normalized_question = question.strip()
        digest = hashlib.sha256(f"question-queries-v1:{item_id}:{normalized_question}".encode()).hexdigest()[:16]
        return self.settings.cache_dir / f"question_{digest}.json"

    def _queries_for_question(self, item: EPLItem, question: str) -> tuple[list[str], bool]:
        cache_path = self._question_cache_path(item.item_id, question)
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                queries = cached.get("queries", [])
                if isinstance(queries, list) and all(isinstance(query, str) and query.strip() for query in queries):
                    return list(dict.fromkeys(query.strip() for query in queries)), True
            except (OSError, json.JSONDecodeError, TypeError, AttributeError):
                # A malformed cache must never break an answer. Replace it with
                # a fresh extraction below.
                pass

        queries = self.llm.extract_queries(item, question)
        cache_path.write_text(
            json.dumps({"item_id": item.item_id, "question": question.strip(), "queries": queries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return queries, False

    def _image_cache_path(self, item: EPLItem) -> Path:
        # Versioned to avoid reusing images cached before team-title validation.
        digest = hashlib.sha256(f"entity-image-v2:{item.item_id}".encode()).hexdigest()[:16]
        return self.settings.cache_dir / f"wiki_image_{digest}.json"

    def _page_image(self, title: str, api_url: str = WIKI_API_URL) -> tuple[str, str]:
        payload = self._request(
            {
                "action": "query",
                "prop": "pageimages|info",
                "piprop": "thumbnail|original",
                "pithumbsize": "360",
                "inprop": "url",
                "redirects": "1",
                "titles": title,
            },
            api_url,
        )
        pages = payload.get("query", {}).get("pages", {})
        page = next(iter(pages.values()), {})
        image = page.get("thumbnail", {}).get("source") or page.get("original", {}).get("source") or ""
        return str(image), str(page.get("fullurl", ""))

    def _summary_image(self, source_url: str) -> tuple[str, str]:
        """Get the lead image from an exact Wikipedia article via its summary API."""
        source_page = _wikipedia_source_page(source_url)
        if not source_page:
            return "", ""
        title, api_url = source_page
        rest_url = api_url.removesuffix("/w/api.php") + f"/api/rest_v1/page/summary/{quote(title, safe='')}"
        self._wait_for_rate_limit()
        response = self.session.get(rest_url, timeout=15)
        response.raise_for_status()
        payload = response.json()
        image = payload.get("thumbnail", {}).get("source") or payload.get("originalimage", {}).get("source") or ""
        canonical_url = payload.get("content_urls", {}).get("desktop", {}).get("page") or source_url
        return str(image), str(canonical_url)

    def profile_image(self, item: EPLItem) -> ProfileImage | None:
        """Return a cached Wikipedia portrait or team crest for a selected entity."""
        if item.item_type not in PLAYER_ITEM_TYPES | TEAM_ITEM_TYPES:
            return None
        image_kind = "팀 로고" if item.item_type in TEAM_ITEM_TYPES else "프로필 사진"
        cache_path = self._image_cache_path(item)
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if cached.get("image_url"):
                    return ProfileImage(item.item_id, item.title, str(cached["image_url"]), str(cached.get("source_url", "")), image_kind)
                return None
            except (OSError, json.JSONDecodeError, TypeError):
                pass

        image_url = source_url = ""
        try:
            if item.item_type in TEAM_ITEM_TYPES:
                image_url, source_url = self._summary_image(str(item.metadata.get("source_url", "")))
            else:
                names = [str(item.metadata.get("player_name_ko", "")), str(item.metadata.get("source_title", ""))]
                for name in dict.fromkeys(name for name in names if name):
                    image_url, source_url = self._page_image(name)
                    if image_url:
                        break
            if not image_url and item.item_type in PLAYER_ITEM_TYPES:
                search_term = str(item.metadata.get("player_name_ko") or item.title)
                for candidate in self.search(search_term, limit=3):
                    if item.item_type in PLAYER_ITEM_TYPES and not external_title_matches_item(item, candidate["title"]):
                        continue
                    image_url, source_url = self._page_image(candidate["title"])
                    if image_url:
                        break
        except requests.RequestException:
            # A profile image is decorative; a temporary API failure must not
            # interrupt RAG collection or answer generation.
            image_url = source_url = ""
        cache_path.write_text(
            json.dumps({"image_url": image_url, "source_url": source_url}, ensure_ascii=False), encoding="utf-8"
        )
        return ProfileImage(item.item_id, item.title, image_url, source_url, image_kind) if image_url else None

    def _valid_documents(self, item: EPLItem, documents: list[ExternalDocument]) -> tuple[list[ExternalDocument], list[str]]:
        """Reject stale or model-selected documents about a different player."""
        valid = [document for document in documents if external_title_matches_item(item, document.title)]
        rejected = [document.title for document in documents if document not in valid]
        return valid, rejected

    @staticmethod
    def _write_cache(cache_path: Path, documents: list[ExternalDocument], audit: dict[str, Any]) -> None:
        cache_path.write_text(
            json.dumps({"documents": [asdict(document) for document in documents], "audit": audit}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def collect_for_query(self, item: EPLItem, question: str, query: str) -> list[ExternalDocument]:
        cache_path = self._cache_path(item.item_id, query)
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            # Supports the early list-only cache format as well as the audited format.
            if isinstance(cached, list):
                documents = [ExternalDocument(**document) for document in cached]
                audit: dict[str, Any] = {"query": query, "selected": [doc.title for doc in documents], "discarded": []}
            else:
                documents = [ExternalDocument(**document) for document in cached.get("documents", [])]
                audit = dict(cached.get("audit", {}))
            documents, rejected = self._valid_documents(item, documents)
            if rejected:
                audit["selected"] = [document.title for document in documents]
                audit["discarded"] = list(dict.fromkeys([*audit.get("discarded", []), *rejected]))
                audit["rejected_as_unrelated"] = rejected
                self._write_cache(cache_path, documents, audit)
            self.last_audits.append({**audit, "cache_hit": True})
            return documents

        try:
            candidates = self.search(query)
        except requests.RequestException:
            # Wikipedia is supplemental. The local JSON fallback remains usable
            # while the next user request can retry external collection.
            self.last_audits.append(
                {"query": query, "selected": [], "discarded": [], "cache_hit": False, "collection_error": "Wikipedia API unavailable"}
            )
            return []
        selected_indices = set(self.llm.choose_candidate_indices(item, question, candidates))
        # The selected subject must be indexed whenever search returns a Korean
        # or English title variant (for example, a bilingual UI display title).
        if item.item_type in PLAYER_ITEM_TYPES:
            selected_indices.update(
                index for index, candidate in enumerate(candidates) if external_title_matches_item(item, candidate["title"])
            )
        else:
            selected_indices.update(
                index for index, candidate in enumerate(candidates) if candidate["title"].casefold() == item.title.casefold()
            )
        rejected_indices = {
            index for index in selected_indices if not external_title_matches_item(item, candidates[index]["title"])
        }
        selected_indices.difference_update(rejected_indices)
        documents: list[ExternalDocument] = []
        for index in sorted(selected_indices):
            candidate = candidates[index]
            try:
                text, url = self.fetch_extract(candidate["title"])
            except requests.RequestException:
                continue
            if not text or not url:
                continue
            document_id = hashlib.sha256(f"{item.item_id}:{url}".encode()).hexdigest()[:24]
            documents.append(
                ExternalDocument(
                    document_id=document_id,
                    related_item_id=item.item_id,
                    title=candidate["title"],
                    text=text,
                    source_url=url,
                    source_type="wikipedia",
                    search_query=query,
                )
            )
        audit = {
            "query": query,
            "selected": [candidates[index]["title"] for index in sorted(selected_indices)],
            "discarded": [candidate["title"] for index, candidate in enumerate(candidates) if index not in selected_indices],
            "rejected_as_unrelated": [candidates[index]["title"] for index in sorted(rejected_indices)],
            "cache_hit": False,
        }
        self.last_audits.append(audit)
        self._write_cache(cache_path, documents, audit)
        return documents

    def collect_for_question(self, item: EPLItem, question: str) -> list[ExternalDocument]:
        self.last_audits = []
        queries, self.last_question_cache_hit = self._queries_for_question(item, question)
        documents: dict[str, ExternalDocument] = {}
        for query in queries:
            for document in self.collect_for_query(item, question, query):
                documents[document.document_id] = document
        if self.last_question_cache_hit:
            for audit in self.last_audits:
                audit["question_cache_hit"] = True
        result = list(documents.values())
        if result:
            self.index_documents(result)
        return result

    def index_documents(self, documents: list[ExternalDocument]) -> int:
        splitter = RecursiveCharacterTextSplitter(chunk_size=self.settings.chunk_size, chunk_overlap=self.settings.chunk_overlap)
        texts: list[str] = []
        metadatas: list[dict[str, str | int | float | bool]] = []
        ids: list[str] = []
        for document in documents:
            for index, chunk in enumerate(splitter.split_text(document.text)):
                texts.append(chunk)
                ids.append(f"{document.related_item_id}:{document.document_id}:{index}")
                metadatas.append(
                    compact_metadata(
                        {
                            "chunk_id": ids[-1],
                            "document_id": document.document_id,
                            "related_item_id": document.related_item_id,
                            "document_title": document.title,
                            "source_url": document.source_url,
                            "source_type": document.source_type,
                            "search_query": document.search_query,
                            "chunk_index": index,
                        }
                    )
                )
        return index_external_chunks(self.settings, texts, metadatas, ids) if texts else 0


def re_strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def _wikipedia_source_page(source_url: str) -> tuple[str, str] | None:
    """Convert a dataset Wikipedia article URL into its matching MediaWiki API URL."""
    parsed = urlparse(source_url)
    if not parsed.netloc.endswith(".wikipedia.org") or not parsed.path.startswith("/wiki/"):
        return None
    title = unquote(parsed.path.removeprefix("/wiki/"))
    if not title:
        return None
    return title, f"{parsed.scheme or 'https'}://{parsed.netloc}/w/api.php"
