"""Print a Korean display-name map for every player present in the local catalogue.

The result is intentionally printed, rather than written to the repository. Review the
JSON and copy it into ``src/player_name_ko.py`` so the application never needs an LLM
call merely to render a name.
"""
from __future__ import annotations

import json
import sys

from openai import OpenAI

from src.config import get_settings
from src.data_loader import load_items


PLAYER_TYPES = {
    "player_current",
    "pfa_player_season",
    "key_player_season",
    "korean_player_profile",
    "korean_player_season",
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    settings = get_settings()
    if not settings.has_api_key:
        raise RuntimeError("GMS_KEY is required to generate the name map.")

    items, _ = load_items(settings.data_dir)
    names = sorted({item.title for item in items if item.item_type in PLAYER_TYPES})
    client = OpenAI(api_key=settings.api_key, base_url=settings.api_base_url)
    response = client.chat.completions.create(
        model=settings.chat_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "developer",
                "content": (
                    "You are an editor for a Korean Premier League service. "
                    "Return exactly one JSON object whose keys are the supplied English player names "
                    "and whose values are their conventional Korean football-media spellings. "
                    "Every supplied name must appear once; do not add explanations, English names, or markdown. "
                    "Keep diacritics and punctuation in keys exactly unchanged."
                ),
            },
            {"role": "user", "content": json.dumps(names, ensure_ascii=False)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    result = json.loads(content)
    if not isinstance(result, dict) or set(result) != set(names):
        missing = sorted(set(names) - set(result)) if isinstance(result, dict) else names
        raise ValueError(f"Model did not return an exact name map. Missing: {missing[:10]}")
    if not all(isinstance(value, str) and value.strip() for value in result.values()):
        raise ValueError("Model returned an empty or invalid Korean name.")
    print(json.dumps(dict(sorted(result.items())), ensure_ascii=False, indent=4))


if __name__ == "__main__":
    main()
