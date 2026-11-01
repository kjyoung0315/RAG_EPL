"""Read missing Korean-player assists from the Premier League statistics API.

This script only prints verified values. It does not alter source JSON; use its
output to review data changes before applying them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.config import get_settings


PLAYER_IDS = {
    "Son Heung-min": 4999,
    "Park Ji-sung": 2940,
    "Ki Sung-yueng": 4656,
}
SEASON_IDS = {
    "2005-06": 14, "2006-07": 15, "2007-08": 16, "2008-09": 17,
    "2009-10": 18, "2010-11": 19, "2011-12": 20, "2012-13": 21,
    "2013-14": 22, "2014-15": 27, "2015-16": 42, "2016-17": 54,
    "2017-18": 79, "2018-19": 210, "2019-20": 274, "2020-21": 363,
    "2021-22": 418, "2022-23": 489, "2023-24": 578, "2024-25": 719,
}
API_URL = "https://footballapi.pulselive.com/football/stats/player/{player_id}"


def official_assists(player_id: int, season_id: int, team_id: int | None = None) -> int:
    query_params = {"comps": 1, "compSeasons": season_id}
    if team_id is not None:
        query_params["teams"] = team_id
    query = urlencode(query_params)
    request = Request(
        f"{API_URL.format(player_id=player_id)}?{query}",
        headers={"Origin": "https://www.premierleague.com", "User-Agent": "EPL-Insight-RAG/1.0"},
    )
    with urlopen(request, timeout=20) as response:  # nosec B310: fixed public read-only API URL
        payload = json.load(response)
    stats = {entry["name"]: entry["value"] for entry in payload["stats"]}
    return int(stats.get("goal_assist", 0))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    data_dir = get_settings().data_dir / "korean_players"
    results: dict[str, int] = {}
    for path in sorted(data_dir.rglob("*.json")):
        if "profiles" in path.parts:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("record_type") != "korean_epl_player_season" or data.get("assists") is not None:
            continue
        relative_path = str(path.relative_to(data_dir))
        team_id = {"ki_sung_yueng\\2013-14_swansea.json": 45, "ki_sung_yueng\\2013-14_sunderland.json": 29}.get(relative_path)
        results[relative_path] = official_assists(
            PLAYER_IDS[data["title"]], SEASON_IDS[data["season"]], team_id
        )
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
