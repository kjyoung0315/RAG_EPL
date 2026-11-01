"""Group the provided current-player JSON files into team squad snapshots."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

# Allow direct execution with `python scripts/generate_team_squads.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import get_settings


def main() -> None:
    settings = get_settings()
    players_dir = settings.data_dir / "players_2026-27"
    output_dir = settings.data_dir / "team_squads_2026-27"
    output_dir.mkdir(parents=True, exist_ok=True)
    squads: dict[str, list[dict[str, object]]] = defaultdict(list)

    for path in sorted(players_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        team_id = str(payload["team_id"])
        squads[team_id].append(payload)

    for team_id, players in sorted(squads.items()):
        players.sort(key=lambda player: (str(player.get("position", "")), int(player.get("shirt_number") or 999), str(player["title"])))
        first = players[0]
        squad = {
            "record_type": "team_squad_snapshot",
            "season": first["season"],
            "title": first["team"],
            "team_id": team_id,
            "team": first["team"],
            "league": first.get("league", "Premier League"),
            "source": "영어 위키백과 구단 선수 명단 기반 제공 데이터",
            "url": first.get("url", ""),
            "collected_at": max(str(player.get("collected_at", "")) for player in players),
            "squad_as_of": max(str(player.get("squad_as_of", "")) for player in players),
            "is_complete_roster": False,
            "completeness_note": "제공된 players_2026-27 데이터에 포함된 선수만 묶은 스냅샷이며, 전체 1군 명단을 보장하지 않습니다.",
            "players": [
                {
                    "name": player["title"],
                    "position": player.get("position", "정보 없음"),
                    "shirt_number": player.get("shirt_number"),
                    "national_team_code": player.get("national_team_code", ""),
                    "is_captain": bool(player.get("is_captain", False)),
                }
                for player in players
            ],
        }
        (output_dir / f"{team_id}.json").write_text(json.dumps(squad, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(squads)}개 팀 선수단 스냅샷을 {output_dir}에 생성했습니다.")


if __name__ == "__main__":
    main()
