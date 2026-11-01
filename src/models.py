from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def compact_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Return only Chroma-compatible scalar metadata values."""
    return {
        key: value
        for key, value in metadata.items()
        if value is not None and isinstance(value, (str, int, float, bool))
    }


@dataclass(frozen=True)
class EPLItem:
    item_id: str
    item_type: str
    title: str
    text: str
    metadata: dict[str, Any]

    def chroma_metadata(self) -> dict[str, str | int | float | bool]:
        return compact_metadata(
            {
                "item_id": self.item_id,
                "item_type": self.item_type,
                "title": self.title,
                "source_type": "local_json",
                **self.metadata,
            }
        )


@dataclass(frozen=True)
class ExternalDocument:
    document_id: str
    related_item_id: str
    title: str
    text: str
    source_url: str
    source_type: str
    search_query: str


@dataclass(frozen=True)
class Evidence:
    label: int
    text: str
    title: str
    source_url: str
    source_type: str
    item_id: str | None = None


@dataclass(frozen=True)
class ProfileImage:
    item_id: str
    title: str
    image_url: str
    source_url: str
    kind: str
