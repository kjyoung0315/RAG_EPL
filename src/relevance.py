from __future__ import annotations

import re
from typing import Any

from src.models import EPLItem


PLAYER_ITEM_TYPES = {
    "player_current",
    "pfa_player_season",
    "key_player_season",
    "korean_player_profile",
    "korean_player_season",
}

TEAM_ITEM_TYPES = {"team_season", "team_current"}


def _normalized(value: object) -> str:
    """Normalize a title for a conservative, language-independent name match."""
    return re.sub(r"[^0-9a-z가-힣]", "", str(value).casefold())


def subject_aliases(item: EPLItem) -> set[str]:
    """Return Korean and English player-name variants supplied by the local dataset."""
    values: list[object] = [item.title]
    values.extend(item.metadata.get(key, "") for key in ("player_name_en", "player_name_ko", "source_title"))
    # A display title such as "스티븐 제라드 (Steven Gerrard)" needs both parts.
    values.extend(re.findall(r"\(([^)]+)\)", item.title))
    return {_normalized(value) for value in values if _normalized(value)}


def external_title_matches_item(item: EPLItem, document_title: object) -> bool:
    """Whether an external document title is safe to associate with this item.

    Strict title checks are intentionally limited to player records. Season and team
    queries can legitimately use documents whose titles differ from the selected
    record (for example, a league-season overview).
    """
    if item.item_type not in PLAYER_ITEM_TYPES:
        return True
    title = _normalized(document_title)
    if not title:
        return False
    return any(alias in title or title in alias for alias in subject_aliases(item))


def metadata_title_matches_item(item: EPLItem, metadata: dict[str, Any]) -> bool:
    return external_title_matches_item(item, metadata.get("document_title", ""))
