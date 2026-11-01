from src.presentation import ITEM_TYPE_LABELS, item_type_label


def test_item_type_labels_are_korean_for_all_catalogue_types() -> None:
    assert item_type_label("key_player_season") == "시즌 주요 선수·수상"
    assert item_type_label("korean_player_profile") == "한국 선수 프로필"
    assert all("_" not in label for label in ITEM_TYPE_LABELS.values())
