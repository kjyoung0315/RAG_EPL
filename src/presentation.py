"""Korean labels and compact rendering helpers for the UI."""

import re

ITEM_TYPE_LABELS = {
    "team_season": "시즌별 팀 성적",
    "team_current": "현재 EPL 팀",
    "team_squad_current": "현재 팀 선수단",
    "player_current": "현재 EPL 선수",
    "pfa_player_season": "PFA 올해의 팀 선정 선수",
    "key_player_season": "시즌 주요 선수·수상",
    "korean_player_season": "한국 선수 시즌 기록",
    "korean_player_profile": "한국 선수 프로필",
    "season_summary": "EPL 시즌 요약",
}


def item_type_label(item_type: str) -> str:
    return ITEM_TYPE_LABELS.get(item_type, item_type)


def compact_answer_markdown(answer: str) -> str:
    """Keep an LLM heading readable inside a chat response instead of oversized."""
    lines: list[str] = []
    for line in answer.splitlines():
        title = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        lines.append(f"**{title.group(1)}**" if title else line)
    return "\n".join(lines)
