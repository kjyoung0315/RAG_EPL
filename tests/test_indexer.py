from src.config import Settings
from src.indexer import ITEM_COLLECTION, collection_count


def test_missing_collection_has_zero_count(tmp_path) -> None:
    settings = Settings(tmp_path, tmp_path, tmp_path / "chroma", tmp_path / "cache", "model", "embed", "", 1000, 200, 5, 10)
    assert collection_count(settings, ITEM_COLLECTION) == 0
