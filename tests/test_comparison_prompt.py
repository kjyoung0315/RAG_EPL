from src.llm import LLMService
from src.models import EPLItem, Evidence


def test_comparison_prompt_binds_targets_and_requests_player_context() -> None:
    left = EPLItem("pfa:2003-04:steven_gerrard", "pfa_player_season", "스티븐 제라드 (Steven Gerrard)", "기록", {})
    right = EPLItem("pfa:2020-21:son_heung_min", "pfa_player_season", "손흥민 (Son Heung-min)", "기록", {})
    llm = object.__new__(LLMService)
    captured: list[str] = []
    llm.invoke = lambda prompt: captured.append(prompt) or "비교 답변"  # type: ignore[method-assign]

    answer = llm.compare_answer(left, right, "성과를 비교해줘", [Evidence(1, "선수 소개", "스티븐 제라드", "", "wikipedia", left.item_id)])

    assert answer == "비교 답변"
    assert "pfa:2003-04:steven_gerrard" in captured[0]
    assert "pfa:2020-21:son_heung_min" in captured[0]
    assert "선수 정보와 기록" in captured[0]
    assert "appearances, goals, assists" in captured[0]
