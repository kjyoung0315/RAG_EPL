from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from src.models import EPLItem
from src.player_name_ko import korean_player_name, player_display_name


INDEXABLE_DIRECTORIES = {
    "teams_historical",
    "teams_2026-27",
    "team_squads_2026-27",
    "players_2026-27",
    "pfa_best11_players",
    "players_historical_key",
    "korean_players",
    "seasons",
}


@dataclass
class LoadReport:
    total_files: int = 0
    invalid_files: list[str] = field(default_factory=list)
    indexed_by_type: Counter[str] = field(default_factory=Counter)
    skipped_by_directory: Counter[str] = field(default_factory=Counter)

    @property
    def indexed_count(self) -> int:
        return sum(self.indexed_by_type.values())


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_") or "unknown"


def _scalar(data: dict[str, Any], key: str) -> str | int | None:
    value = data.get(key)
    return value if isinstance(value, (str, int)) else None


def _source_url(data: dict[str, Any]) -> str:
    value = data.get("source_url") or data.get("url") or data.get("wikipedia_search_url")
    return str(value) if value else ""


def _base_metadata(data: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        "season": _scalar(data, "season"),
        "team": _scalar(data, "team"),
        "player": _scalar(data, "player") or _scalar(data, "title"),
        "source_name": _scalar(data, "source") or "EPL JSON dataset",
        "source_url": _source_url(data),
        "source_path": path.as_posix(),
        "collected_at": _scalar(data, "collected_at"),
        "verification_status": _scalar(data, "verification_status"),
    }


def _player_identity(data: dict[str, Any], path: Path) -> tuple[str, str, dict[str, Any]]:
    """Keep source names stable while exposing Korean-first names to the UI and RAG."""
    english_name = str(data["title"])
    korean_name = korean_player_name(english_name)
    display_name = player_display_name(english_name)
    return english_name, display_name, {
        **_base_metadata(data, path),
        "player": display_name,
        "player_name_en": english_name,
        "player_name_ko": korean_name,
        "source_title": english_name,
    }


def _team_season(data: dict[str, Any], path: Path) -> EPLItem:
    team, season = str(data["title"]), str(data["season"])
    stats = data.get("season_stats", {})
    text = (
        f"{season} 프리미어리그 {team}의 최종 성적이다. "
        f"순위 {stats.get('rank')}위, {stats.get('played')}경기, "
        f"{stats.get('wins')}승 {stats.get('draws')}무 {stats.get('losses')}패, "
        f"승점 {stats.get('points')}점. 득점 {stats.get('goals_for')}, "
        f"실점 {stats.get('goals_against')}, 득실차 {stats.get('goal_difference')}이다."
    )
    return EPLItem(
        f"team:{season}:{slug(team)}", "team_season", team, text,
        {**_base_metadata(data, path), "team": team, "rank": stats.get("rank"), "points": stats.get("points")},
    )


def _current_team(data: dict[str, Any], path: Path) -> EPLItem:
    title, season = str(data["title"]), str(data.get("season", "2026-27"))
    stats = data.get("season_stats", {})
    text = (
        f"{season} 프리미어리그 참가 팀 {title}. 홈구장 {data.get('stadium', '정보 없음')}, "
        f"연고지 {data.get('city', '정보 없음')}, 감독 {data.get('manager', '정보 없음')}, "
        f"주장 {data.get('captain', '정보 없음')}. 수집 시점 리그 순위 {stats.get('rank', '정보 없음')}위, "
        f"승점 {stats.get('points', '정보 없음')}점이다. 이 기록은 수집 시점 스냅샷이다."
    )
    return EPLItem(f"team_current:{slug(title)}", "team_current", title, text, _base_metadata(data, path))


def _current_player(data: dict[str, Any], path: Path) -> EPLItem:
    source_title, title, metadata = _player_identity(data, path)
    team = str(data.get("team", ""))
    season = str(data.get("season", "2026-27"))
    text = (
        f"{season} 시즌 {team} 소속 선수 {title}. 포지션은 {data.get('position', '정보 없음')}, "
        f"등번호는 {data.get('shirt_number', '정보 없음')}, 국가대표 코드는 "
        f"{data.get('national_team_code', '정보 없음')}이다. 이 명단은 수집 시점 기준이다."
    )
    return EPLItem(f"player_current:{slug(team)}:{slug(source_title)}", "player_current", title, text, metadata)


def _team_squad(data: dict[str, Any], path: Path) -> EPLItem:
    team, season = str(data["team"]), str(data["season"])
    players = data.get("players", [])
    roster: list[str] = []
    for player in players if isinstance(players, list) else []:
        if not isinstance(player, dict) or not player.get("name"):
            continue
        name = str(player["name"])
        roster.append(
            f"{player_display_name(name)}"
            f"({player.get('position', '정보 없음')}, 등번호 {player.get('shirt_number', '정보 없음')})"
        )
    completeness = "전체 1군 명단이 아닌 제공 데이터 기준 스냅샷이다." if not data.get("is_complete_roster") else "전체 1군 명단이다."
    text = (
        f"{season} 시즌 {team} 현재 선수단 스냅샷. 제공 데이터에서 확인된 선수는 {len(roster)}명이다: "
        f"{'; '.join(roster) or '선수 정보 없음'}. 기준일 {data.get('squad_as_of', '정보 없음')}. {completeness}"
    )
    return EPLItem(
        f"team_squad_current:{slug(team)}",
        "team_squad_current",
        f"{team} 현재 선수단",
        text,
        {
            **_base_metadata(data, path),
            "team": team,
            "squad_player_count": len(roster),
            "squad_as_of": _scalar(data, "squad_as_of"),
            "is_complete_roster": bool(data.get("is_complete_roster")),
        },
    )


def _pfa_player(data: dict[str, Any], path: Path) -> EPLItem:
    source_title, title, metadata = _player_identity(data, path)
    season, team = str(data["season"]), str(data["team"])
    text = (
        f"{title}은(는) {season} 시즌 {team} 소속으로 PFA Premier League Team of the Year에 "
        f"{data.get('position_group', '정보 없음')} 포지션으로 선정됐다."
    )
    return EPLItem(f"pfa:{season}:{slug(source_title)}", "pfa_player_season", title, text, metadata)


def _key_player(data: dict[str, Any], path: Path) -> EPLItem:
    source_title, title, metadata = _player_identity(data, path)
    season, team = str(data["season"]), str(data["team"])
    awards = data.get("awards", {})
    honours: list[str] = []
    if awards.get("player_of_the_season"):
        honours.append("프리미어리그 시즌 최우수 선수")
    if awards.get("golden_boot"):
        honours.append(f"득점왕 {data.get('goals_if_golden_boot')}골")
    text = f"{season} 시즌 {team}의 {title}. 주요 성과: {', '.join(honours) or '기록 없음'}."
    return EPLItem(f"player_season:{season}:{slug(source_title)}", "key_player_season", title, text, metadata)


def _korean_player(data: dict[str, Any], path: Path) -> EPLItem:
    source_title, title, metadata = _player_identity(data, path)
    if data.get("record_type") == "korean_epl_player_profile":
        text = f"대한민국 EPL 선수 프로필: {data.get('name_ko', title)}({source_title}). {data.get('text', '')}"
        return EPLItem(f"korean_profile:{slug(source_title)}", "korean_player_profile", title, text, metadata)
    season, team = str(data["season"]), str(data["team"])
    metadata = {
        **metadata,
        "assists_source": "Premier League official statistics API (goal_assist)",
        "assists_source_url": "https://www.premierleague.com/en/stats/top/players/goal_assist",
    }
    text = (
        f"대한민국 선수 {data.get('name_ko', title)}({source_title})의 {season} 시즌 {team} EPL 기록. "
        f"출전 {data.get('appearances', '정보 없음')}경기, 득점 {data.get('goals', '정보 없음')}골, "
        f"도움 {data.get('assists', '정보 없음')}개다. 도움은 프리미어리그 공식 통계 기준이다."
    )
    return EPLItem(f"korean_player:{season}:{slug(source_title)}:{slug(team)}", "korean_player_season", title, text, metadata)


def _season(data: dict[str, Any], path: Path) -> EPLItem:
    season, champion = str(data["season"]), str(data.get("champion", "정보 없음"))
    text = f"{season} 잉글랜드 프리미어리그 시즌 요약. 우승팀은 {champion}이다."
    return EPLItem(f"season:{season}", "season_summary", data.get("title", season), text, _base_metadata(data, path))


def normalize_file(data: dict[str, Any], relative_path: Path) -> EPLItem | None:
    root = relative_path.parts[0] if relative_path.parts else ""
    if root == "teams_historical":
        return _team_season(data, relative_path)
    if root == "teams_2026-27":
        return _current_team(data, relative_path)
    if root == "players_2026-27":
        return _current_player(data, relative_path)
    if root == "team_squads_2026-27":
        return _team_squad(data, relative_path)
    if root == "pfa_best11_players":
        return _pfa_player(data, relative_path)
    if root == "players_historical_key":
        return _key_player(data, relative_path)
    if root == "korean_players":
        return _korean_player(data, relative_path)
    if root == "seasons":
        return _season(data, relative_path)
    return None


def load_items(data_dir: Path) -> tuple[list[EPLItem], LoadReport]:
    report = LoadReport()
    items: list[EPLItem] = []
    seen_ids: set[str] = set()
    for path in sorted(data_dir.rglob("*.json")):
        report.total_files += 1
        relative = path.relative_to(data_dir)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            report.invalid_files.append(relative.as_posix())
            continue
        if not isinstance(payload, dict):
            report.skipped_by_directory[relative.parts[0] if relative.parts else "root"] += 1
            continue
        item = normalize_file(payload, relative)
        if item is None:
            report.skipped_by_directory[relative.parts[0] if relative.parts else "root"] += 1
            continue
        if item.item_id in seen_ids:
            raise ValueError(f"Duplicate normalized item id: {item.item_id}")
        seen_ids.add(item.item_id)
        items.append(item)
        report.indexed_by_type[item.item_type] += 1
    return items, report


def item_lookup(items: Iterable[EPLItem]) -> dict[str, EPLItem]:
    return {item.item_id: item for item in items}
