from langchain_core.documents import Document

from src.models import EPLItem
from src.retriever import EPLRetriever


class FakeExternalStore:
    def similarity_search(self, question: str, k: int, filter: dict[str, str]) -> list[Document]:
        assert filter == {"related_item_id": "player:son"}
        return [
            Document(
                page_content="위키백과에서 수집한 손흥민 문서 본문",
                metadata={
                    "document_title": "손흥민",
                    "source_url": "https://ko.wikipedia.org/wiki/손흥민",
                    "source_type": "위키백과 API",
                },
            )
        ]


class MixedPlayerExternalStore:
    def similarity_search(self, question: str, k: int, filter: dict[str, str]) -> list[Document]:
        return [
            Document(page_content="베컴 문서", metadata={"document_title": "데이비드 베컴", "source_url": "https://example.com/beckham"}),
            Document(page_content="제라드 문서", metadata={"document_title": "스티븐 제라드", "source_url": "https://example.com/gerrard"}),
        ]


class EmptyTeamExternalStore:
    def similarity_search(self, question: str, k: int, filter: dict[str, str]) -> list[Document]:
        assert filter == {"related_item_id": "team_current:liverpool"}
        return []


def test_wikipedia_evidence_precedes_the_local_json_fallback() -> None:
    retriever = object.__new__(EPLRetriever)
    retriever.external_store = FakeExternalStore()
    retriever.top_k = 5
    item = EPLItem("player:son", "player", "손흥민 (Son Heung-min)", "로컬 JSON 본문", {})

    evidence = retriever.retrieve(item, "손흥민은 누구인가요?")

    assert [entry.source_type for entry in evidence] == ["위키백과 API", "EPL 로컬 JSON (보완 근거)"]
    assert [entry.label for entry in evidence] == [1, 2]
    assert evidence[0].title == "손흥민"


def test_stale_external_chunk_for_another_player_is_filtered() -> None:
    retriever = object.__new__(EPLRetriever)
    retriever.external_store = MixedPlayerExternalStore()
    retriever.top_k = 5
    item = EPLItem(
        "pfa:2003-04:steven_gerrard",
        "pfa_player_season",
        "스티븐 제라드 (Steven Gerrard)",
        "로컬 제라드 기록",
        {"player_name_en": "Steven Gerrard", "player_name_ko": "스티븐 제라드"},
    )

    evidence = retriever.retrieve(item, "PFA 선정 기록")

    assert [entry.title for entry in evidence] == ["스티븐 제라드", "스티븐 제라드 (Steven Gerrard)"]


def test_current_team_question_includes_its_local_squad_snapshot() -> None:
    retriever = object.__new__(EPLRetriever)
    retriever.external_store = EmptyTeamExternalStore()
    retriever.top_k = 5
    squad = EPLItem(
        "team_squad_current:liverpool",
        "team_squad_current",
        "Liverpool 현재 선수단",
        "Liverpool 현재 선수단 스냅샷: 알리송 베케르, 버질 판 데이크.",
        {"team": "Liverpool"},
    )
    retriever.team_squads = {"Liverpool": squad}
    team = EPLItem("team_current:liverpool", "team_current", "Liverpool", "Liverpool 팀 정보", {"team": "Liverpool"})

    evidence = retriever.retrieve(team, "리버풀 선수단을 알려줘")

    assert [entry.source_type for entry in evidence] == ["EPL 로컬 JSON (현재 선수단)", "EPL 로컬 JSON (보완 근거)"]
    assert "알리송 베케르" in evidence[0].text
