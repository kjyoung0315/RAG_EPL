from pathlib import Path

import requests

from src.collector import WikipediaCollector, _wikipedia_source_page, re_strip_html
from src.config import Settings
from src.models import EPLItem


def test_wikipedia_snippet_html_is_cleaned() -> None:
    assert re_strip_html('EPL <span class="searchmatch">우승</span> &amp; 기록') == "EPL 우승 & 기록"


class FakeLLM:
    def choose_candidate_indices(self, item: EPLItem, question: str, candidates: list[dict[str, str]]) -> list[int]:
        return [1]


class QuestionCacheLLM(FakeLLM):
    def __init__(self) -> None:
        self.extract_calls = 0

    def extract_queries(self, item: EPLItem, question: str) -> list[str]:
        self.extract_calls += 1
        return ["same query"]


class FakeCollector(WikipediaCollector):
    def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        return [{"title": "제외 문서", "snippet": ""}, {"title": "선택 문서", "snippet": ""}]

    def fetch_extract(self, title: str) -> tuple[str, str]:
        return f"{title} 본문", f"https://example.com/{title}"


class CountingCollector(FakeCollector):
    def __init__(self, settings: Settings, llm: QuestionCacheLLM) -> None:
        super().__init__(settings, llm)
        self.search_calls = 0

    def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        self.search_calls += 1
        return super().search(query, limit)


class PlayerCandidateCollector(FakeCollector):
    def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        return [{"title": "스티븐 제라드", "snippet": ""}, {"title": "데이비드 베컴", "snippet": ""}]


class ImageCollector(WikipediaCollector):
    def __init__(self, settings: Settings, llm: FakeLLM) -> None:
        super().__init__(settings, llm)
        self.image_requests = 0

    def _page_image(self, title: str) -> tuple[str, str]:
        self.image_requests += 1
        return "https://images.example.com/gerrard.jpg", "https://ko.wikipedia.org/wiki/스티븐_제라드"


class UnavailableWikipediaCollector(FakeCollector):
    def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        raise requests.ConnectionError("Wikipedia unavailable")


class TeamImageCollector(WikipediaCollector):
    def __init__(self, settings: Settings, llm: FakeLLM) -> None:
        super().__init__(settings, llm)
        self.source_request = ""

    def _summary_image(self, source_url: str) -> tuple[str, str]:
        self.source_request = source_url
        return "https://images.example.com/chelsea.png", "https://en.wikipedia.org/wiki/Chelsea_F.C."


def test_candidate_audit_and_cache_are_saved(tmp_path: Path) -> None:
    settings = Settings(tmp_path, tmp_path, tmp_path / "chroma", tmp_path / "cache", "model", "embed", "", 1000, 200, 5, 10)
    item = EPLItem("season:2000-01", "season_summary", "2000-01", "시즌 요약", {})
    collector = FakeCollector(settings, FakeLLM())
    documents = collector.collect_for_query(item, "질문", "검색어")
    assert [document.title for document in documents] == ["선택 문서"]
    assert collector.last_audits[0]["discarded"] == ["제외 문서"]

    cached = collector.collect_for_query(item, "질문", "검색어")
    assert [document.title for document in cached] == ["선택 문서"]
    assert collector.last_audits[-1]["cache_hit"] is True


def test_same_question_uses_question_and_document_caches(tmp_path: Path) -> None:
    settings = Settings(tmp_path, tmp_path, tmp_path / "chroma", tmp_path / "cache", "model", "embed", "", 1000, 200, 5, 10)
    item = EPLItem("season:2000-01", "season_summary", "2000-01", "season summary", {})
    llm = QuestionCacheLLM()
    collector = CountingCollector(settings, llm)
    # Indexing is not part of this cache contract and needs no vector service.
    collector.index_documents = lambda documents: 0  # type: ignore[method-assign]

    first = collector.collect_for_question(item, "same question")
    second = collector.collect_for_question(item, "same question")

    assert second == first
    assert llm.extract_calls == 1
    assert collector.search_calls == 1
    assert collector.last_question_cache_hit is True
    assert collector.last_audits
    assert all(audit["cache_hit"] is True for audit in collector.last_audits)
    assert all(audit["question_cache_hit"] is True for audit in collector.last_audits)


def test_player_candidate_from_another_person_is_never_cached(tmp_path: Path) -> None:
    settings = Settings(tmp_path, tmp_path, tmp_path / "chroma", tmp_path / "cache", "model", "embed", "", 1000, 200, 5, 10)
    item = EPLItem(
        "pfa:2003-04:steven_gerrard",
        "pfa_player_season",
        "스티븐 제라드 (Steven Gerrard)",
        "제라드 기록",
        {"player_name_en": "Steven Gerrard", "player_name_ko": "스티븐 제라드"},
    )
    collector = PlayerCandidateCollector(settings, FakeLLM())

    documents = collector.collect_for_query(item, "비교", "제라드 PFA")

    assert [document.title for document in documents] == ["스티븐 제라드"]
    assert collector.last_audits[0]["rejected_as_unrelated"] == ["데이비드 베컴"]

    # The persisted cache is also sanitized when a previous app version saved it.
    cache_path = collector._cache_path(item.item_id, "오염된 캐시")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        '{"documents": [{"document_id": "1", "related_item_id": "pfa:2003-04:steven_gerrard", "title": "데이비드 베컴", "text": "본문", "source_url": "https://example.com/beckham", "source_type": "wikipedia", "search_query": "오염된 캐시"}]}',
        encoding="utf-8",
    )
    assert collector.collect_for_query(item, "비교", "오염된 캐시") == []
    persisted = __import__("json").loads(cache_path.read_text(encoding="utf-8"))
    assert persisted["documents"] == []


def test_player_profile_image_is_cached(tmp_path: Path) -> None:
    settings = Settings(tmp_path, tmp_path, tmp_path / "chroma", tmp_path / "cache", "model", "embed", "", 1000, 200, 5, 10)
    item = EPLItem(
        "pfa:2003-04:steven_gerrard",
        "pfa_player_season",
        "스티븐 제라드 (Steven Gerrard)",
        "제라드 기록",
        {"player_name_en": "Steven Gerrard", "player_name_ko": "스티븐 제라드"},
    )
    collector = ImageCollector(settings, FakeLLM())

    image = collector.profile_image(item)
    cached = collector.profile_image(item)

    assert image is not None
    assert image.image_url == "https://images.example.com/gerrard.jpg"
    assert cached == image
    assert collector.image_requests == 1


def test_wikipedia_outage_does_not_interrupt_collection(tmp_path: Path) -> None:
    settings = Settings(tmp_path, tmp_path, tmp_path / "chroma", tmp_path / "cache", "model", "embed", "", 1000, 200, 5, 10)
    item = EPLItem("season:2000-01", "season_summary", "2000-01", "시즌 요약", {})
    collector = UnavailableWikipediaCollector(settings, FakeLLM())

    assert collector.collect_for_query(item, "질문", "검색어") == []
    assert collector.last_audits[0]["collection_error"] == "Wikipedia API unavailable"


def test_team_logo_uses_the_dataset_wikipedia_article(tmp_path: Path) -> None:
    settings = Settings(tmp_path, tmp_path, tmp_path / "chroma", tmp_path / "cache", "model", "embed", "", 1000, 200, 5, 10)
    item = EPLItem(
        "team_current:chelsea",
        "team_current",
        "Chelsea",
        "팀 정보",
        {"source_url": "https://en.wikipedia.org/wiki/Chelsea_F.C."},
    )
    collector = TeamImageCollector(settings, FakeLLM())

    image = collector.profile_image(item)

    assert image is not None
    assert image.kind == "팀 로고"
    assert collector.source_request == "https://en.wikipedia.org/wiki/Chelsea_F.C."
    assert _wikipedia_source_page("https://en.wikipedia.org/wiki/Chelsea_F.C.") == (
        "Chelsea_F.C.",
        "https://en.wikipedia.org/w/api.php",
    )
