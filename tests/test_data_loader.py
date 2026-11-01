from src.config import get_settings
from src.data_loader import load_items
from src.player_name_ko import PLAYER_NAME_KO, player_display_name


def test_dataset_normalizes_enough_items() -> None:
    items, report = load_items(get_settings().data_dir)
    assert report.total_files == 837
    assert not report.invalid_files
    assert len(items) >= 600
    assert len({item.item_id for item in items}) == len(items)


def test_team_squad_snapshots_are_loaded_with_their_available_players() -> None:
    items, _ = load_items(get_settings().data_dir)
    squads = [item for item in items if item.item_type == "team_squad_current"]
    liverpool = next(item for item in squads if item.item_id == "team_squad_current:liverpool")
    assert len(squads) == 20
    assert liverpool.metadata["squad_player_count"] == 6
    assert "알리송 베케르" in liverpool.text
    assert "전체 1군 명단이 아닌" in liverpool.text


def test_team_season_uses_structured_stats_not_broken_source_text() -> None:
    items, _ = load_items(get_settings().data_dir)
    item = next(item for item in items if item.item_id == "team:2000-01:manchester_united")
    assert "24승 8무 6패" in item.text


def test_player_names_are_korean_first_with_the_source_name_preserved() -> None:
    items, _ = load_items(get_settings().data_dir)
    son = next(item for item in items if item.item_id == "pfa:2020-21:son_heung_min")
    assert son.title == "손흥민 (Son Heung-min)"
    assert son.metadata["player_name_ko"] == "손흥민"
    assert son.metadata["player_name_en"] == "Son Heung-min"
    assert player_display_name("Son Heung-min") == son.title


def test_every_bundled_player_has_a_korean_display_name() -> None:
    items, _ = load_items(get_settings().data_dir)
    player_items = [item for item in items if "player" in item.item_type]
    source_names = {str(item.metadata["player_name_en"]) for item in player_items}
    assert source_names <= set(PLAYER_NAME_KO)


def test_korean_player_season_assists_are_not_missing() -> None:
    items, _ = load_items(get_settings().data_dir)
    korean_seasons = [item for item in items if item.item_type == "korean_player_season"]
    assert len(korean_seasons) == 27
    assert all("도움 None" not in item.text for item in korean_seasons)
    son = next(item for item in korean_seasons if item.item_id == "korean_player:2024-25:son_heung_min:tottenham_hotspur")
    assert "도움 9개" in son.text
