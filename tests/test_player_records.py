from src.models import EPLItem
from src.player_records import player_record_summary, record_summary_markdown
from src.presentation import compact_answer_markdown


def test_player_record_summary_includes_pfa_count_and_selected_season_stats() -> None:
    pfa = EPLItem(
        "pfa:2020-21:son_heung_min",
        "pfa_player_season",
        "손흥민 (Son Heung-min)",
        "손흥민은 2020-21 시즌 Tottenham Hotspur 소속으로 PFA Premier League Team of the Year에 FW 포지션으로 선정됐다.",
        {"player_name_en": "Son Heung-min", "season": "2020-21", "team": "Tottenham Hotspur"},
    )
    season = EPLItem(
        "korean_player:2020-21:son_heung_min:tottenham_hotspur",
        "korean_player_season",
        "손흥민 (Son Heung-min)",
        "대한민국 선수 손흥민의 2020-21 시즌 Tottenham Hotspur EPL 기록. 출전 37경기, 득점 17골, 도움 10개다.",
        {"player_name_en": "Son Heung-min", "season": "2020-21", "team": "Tottenham Hotspur"},
    )

    summary = player_record_summary(pfa, [pfa, season])

    assert summary is not None
    assert "총 1회" in summary.text
    assert "출전 37경기, 득점 17골, 도움 10개" in summary.text
    summary = summary.__class__(3, summary.text, summary.title, summary.source_url, summary.source_type, summary.item_id)
    assert "[근거 3]" in record_summary_markdown([summary])


def test_markdown_headings_are_rendered_as_compact_bold_labels() -> None:
    assert compact_answer_markdown("## 비교 결과\n내용") == "**비교 결과**\n내용"
