from __future__ import annotations

import re
from collections.abc import Iterable

from src.models import EPLItem, Evidence


def player_record_summary(item: EPLItem, items: Iterable[EPLItem]) -> Evidence | None:
    """Build a deterministic local-record summary for a player comparison."""
    player_name = item.metadata.get("player_name_en")
    if not player_name:
        return None
    player_items = [entry for entry in items if entry.metadata.get("player_name_en") == player_name]
    pfa_items = sorted(
        (entry for entry in player_items if entry.item_type == "pfa_player_season"),
        key=lambda entry: str(entry.metadata.get("season", "")),
    )
    parts: list[str] = []
    if pfa_items:
        seasons = ", ".join(str(entry.metadata.get("season")) for entry in pfa_items)
        teams = ", ".join(dict.fromkeys(str(entry.metadata.get("team")) for entry in pfa_items if entry.metadata.get("team")))
        positions = ", ".join(dict.fromkeys(_pfa_position(entry.text) for entry in pfa_items if _pfa_position(entry.text)))
        parts.append(
            f"프로젝트 로컬 데이터에서 확인된 PFA Premier League Team of the Year 선정은 총 {len(pfa_items)}회"
            f"({seasons})이며, 소속 팀은 {teams or '확인되지 않음'}, 포지션은 {positions or '확인되지 않음'}이다."
        )

    selected_season = str(item.metadata.get("season", ""))
    season_records = [
        entry
        for entry in player_items
        if entry.item_type == "korean_player_season" and str(entry.metadata.get("season", "")) == selected_season
    ]
    for record in season_records:
        stats = _season_stats(record.text)
        if stats:
            appearances, goals, assists = stats
            parts.append(
                f"{selected_season} EPL 시즌 기록은 {record.metadata.get('team', '소속 팀 미상')}에서 "
                f"출전 {appearances}경기, 득점 {goals}골, 도움 {assists}개다."
            )

    if not parts:
        return None
    return Evidence(
        label=0,
        text=f"{item.title}의 EPL 로컬 기록 요약. " + " ".join(parts),
        title=f"{item.title} — EPL 로컬 선수 기록 요약",
        source_url="",
        source_type="EPL 로컬 JSON (선수 기록 요약)",
        item_id=item.item_id,
    )


def record_summary_markdown(evidence: Iterable[Evidence]) -> str:
    """Render guaranteed, compact player-record facts before the generated analysis."""
    summaries = [entry for entry in evidence if entry.source_type == "EPL 로컬 JSON (선수 기록 요약)"]
    if not summaries:
        return ""
    lines = ["**선수 기록 요약**"]
    lines.extend(f"- {entry.text} [근거 {entry.label}]" for entry in summaries)
    return "\n".join(lines)


def _pfa_position(text: str) -> str:
    match = re.search(r"\b(MF|FW|DF|GK)\b", text)
    return match.group(1) if match else ""


def _season_stats(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"출전\s*(\d+)경기,\s*득점\s*(\d+)골,\s*도움\s*(\d+)개", text)
    if not match:
        return None
    return tuple(int(value) for value in match.groups())
