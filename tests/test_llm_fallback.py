from src.llm import LLMService
from src.models import EPLItem, Evidence


def _raise_connection_error(_: str) -> str:
    raise ConnectionError("gateway unavailable")


def test_query_extraction_uses_deterministic_fallback_when_gateway_is_down() -> None:
    llm = object.__new__(LLMService)
    llm.invoke = _raise_connection_error  # type: ignore[method-assign]
    item = EPLItem("pfa:2003-04:steven_gerrard", "pfa_player_season", "스티븐 제라드 (Steven Gerrard)", "기록", {"season": "2003-04"})

    assert llm.extract_queries(item, "기록을 알려줘") == ["스티븐 제라드 (Steven Gerrard) 2003-04 Premier League"]


def test_answer_shows_evidence_when_gateway_is_down() -> None:
    llm = object.__new__(LLMService)
    llm.invoke = _raise_connection_error  # type: ignore[method-assign]
    evidence = [Evidence(1, "확인된 로컬 기록", "선수", "", "EPL 로컬 JSON", "player:test")]

    answer = llm.answer("기록을 알려줘", evidence)

    assert "AI 응답 서버 연결" in answer
    assert "확인된 로컬 기록" in answer
    assert "[근거 1]" in answer
