from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

from src.config import get_settings
from src.data_loader import item_lookup, load_items
from src.indexer import ITEM_COLLECTION, collection_count, index_items, is_item_index_current
from src.models import EPLItem, ProfileImage
from src.presentation import compact_answer_markdown, item_type_label
from src.service import AnswerResult, EPLService


st.set_page_config(page_title="EPL Insight RAG", page_icon="⚽", layout="wide")
SERVICE_CACHE_VERSION = "stadium-music-v1"
STADIUM_LOOP_FILE = Path(__file__).resolve().parent / "assets" / "epl_stadium_loop.wav"


def inject_styles() -> None:
    st.markdown(
        """
        <style>
          :root { --ink: #17233b; --navy: #101b36; --blue: #2d65dd; --mint: #38d5bd; --mist: #f4f7fc; }
          .stApp { background: radial-gradient(circle at 78% -8%, #deecff 0, transparent 28rem), #f7f9fc; color: var(--ink); }
          .block-container { max-width: 1440px; padding-top: 2rem; padding-bottom: 7rem; }
          [data-testid="stSidebar"] { background: linear-gradient(180deg, #0d1730 0%, #152751 100%); }
          [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] [data-testid="stMetricLabel"], [data-testid="stSidebar"] [data-testid="stMetricValue"] { color: #edf4ff; }
          [data-testid="stSidebar"] [data-baseweb="select"] > div { background: rgba(255,255,255,.09); border-color: rgba(255,255,255,.16); }
          [data-testid="stSidebar"] [data-baseweb="select"] > div * { color: #edf4ff; }
          [data-baseweb="popover"] { background: #fff !important; }
          [data-baseweb="popover"] [role="option"], [data-baseweb="popover"] [role="option"] * { color: #17233b !important; background: #fff !important; }
          [data-baseweb="popover"] [role="option"]:hover, [data-baseweb="popover"] [role="option"]:hover * { background: #eef4ff !important; color: #245ac8 !important; }
          [data-testid="stSidebar"] .stCaption { color: #adc2e9 !important; }
          [data-testid="stSidebar"] [data-testid="stMetric"] { background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.10); border-radius: 14px; padding: .65rem .75rem; }
          [data-testid="stSidebar"] [data-testid="stMetricValue"] { color: #5be2c8; }
          .epl-brand { padding: .4rem 0 1.2rem; }
          .epl-brand__mark { display: inline-block; color: #57e0c7; font-size: .78rem; font-weight: 800; letter-spacing: .14em; }
          .epl-brand__name { margin: .35rem 0 .3rem; color: #fff; font-size: 1.58rem; font-weight: 800; letter-spacing: -.04em; }
          .epl-brand__sub { color: #abc0e6; font-size: .79rem; line-height: 1.55; }
          .hero { position: relative; overflow: hidden; border-radius: 24px; padding: 2rem 2.2rem; margin-bottom: 1.3rem; background: linear-gradient(120deg, #101b36 0%, #18346a 57%, #2d65dd 135%); box-shadow: 0 18px 42px rgba(18, 48, 104, .18); }
          .hero:after { content: '⚽'; position: absolute; right: 2.1rem; top: -.9rem; font-size: 8rem; opacity: .10; transform: rotate(-12deg); }
          .hero__eyebrow { color: #6ce6d0; font-size: .78rem; font-weight: 800; letter-spacing: .14em; }
          .hero h1 { position: relative; margin: .4rem 0 .55rem; color: #fff; font-size: clamp(1.8rem, 3vw, 2.65rem); letter-spacing: -.055em; }
          .hero p { position: relative; max-width: 46rem; margin: 0; color: #c8d9f8; font-size: 1rem; line-height: 1.6; }
          .context-card { display: flex; gap: 1rem; align-items: flex-start; padding: 1.15rem 1.25rem; margin: .4rem 0 1.1rem; border: 1px solid #dce5f3; border-radius: 16px; background: rgba(255,255,255,.82); box-shadow: 0 8px 22px rgba(31, 54, 96, .06); }
          .context-card__badge { flex: 0 0 auto; padding: .31rem .55rem; border-radius: 999px; background: #e7efff; color: #245ac8; font-size: .73rem; font-weight: 800; }
          .context-card__title { color: #17233b; font-size: 1.03rem; font-weight: 800; }
          .context-card__text { margin-top: .28rem; color: #63718a; font-size: .88rem; line-height: 1.55; }
          [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: .35rem; border-bottom: 1px solid #dce4f0; }
          [data-testid="stTabs"] [data-baseweb="tab"] { height: 42px; padding: 0 1rem; color: #63718a; font-weight: 700; }
          [data-testid="stTabs"] [aria-selected="true"] { color: #245ac8; }
          [data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: #2d65dd; height: 3px; }
          [data-testid="stChatMessage"] { border: 1px solid #e1e8f3; border-radius: 16px; padding: .55rem .85rem; background: rgba(255,255,255,.8); box-shadow: 0 5px 15px rgba(28, 51, 92, .04); }
          [data-testid="stChatMessage"][data-testid] { margin-bottom: .65rem; }
          [data-testid="stChatInput"] { border-radius: 15px; box-shadow: 0 10px 28px rgba(22, 43, 82, .14); }
          .stButton > button { border: 0; border-radius: 10px; background: linear-gradient(120deg, #2d65dd, #3c85ea); color: #fff; font-weight: 750; box-shadow: 0 6px 14px rgba(45,101,221,.18); }
          .stButton > button:hover { border: 0; color: #fff; transform: translateY(-1px); }
          [data-baseweb="select"] > div, .stTextInput input { border-radius: 10px !important; border-color: #d9e2f0 !important; background: #fff !important; }
          [data-testid="stExpander"] { border: 1px solid #dfe6f1; border-radius: 14px; background: rgba(255,255,255,.72); }
          [data-testid="stImage"] img { border-radius: 14px; border: 3px solid #fff; box-shadow: 0 8px 18px rgba(27, 50, 91, .12); }
          @media (max-width: 700px) { .block-container { padding: 1rem 1rem 6rem; } .hero { padding: 1.45rem; border-radius: 18px; } .hero:after { right: .6rem; font-size: 5.5rem; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_styles()


@st.cache_data(show_spinner=False)
def load_catalog() -> tuple[list[EPLItem], dict[str, EPLItem], dict[str, int]]:
    settings = get_settings()
    items, report = load_items(settings.data_dir)
    return items, item_lookup(items), dict(report.indexed_by_type)


@st.cache_resource(show_spinner=False)
def get_service() -> EPLService:
    # Bump this when service behavior changes so a running Streamlit process
    # does not retain an older cached EPLService instance.
    _ = SERVICE_CACHE_VERSION
    return EPLService(get_settings())


def item_label(item: EPLItem) -> str:
    season = item.metadata.get("season")
    team = item.metadata.get("team")
    suffix = " · ".join(str(value) for value in (season, team) if value)
    return f"[{item_type_label(item.item_type)}] {item.title}" + (f" — {suffix}" if suffix else "")


def render_evidence(result: AnswerResult) -> None:
    cited_labels = {int(value) for value in __import__("re").findall(r"\[근거\s*(\d+)\]", result.answer)}
    cited = [entry for entry in result.evidence if entry.label in cited_labels]
    if not cited:
        return
    with st.expander(f"답변 근거 · {len(cited)}개", expanded=False):
        for entry in cited:
            source = f" · [원문 보기]({entry.source_url})" if entry.source_url else ""
            st.markdown(f"**[근거 {entry.label}] {entry.title}** — `{entry.source_type}`{source}")


def render_profile_images(images: list[ProfileImage]) -> None:
    if not images:
        return
    columns = st.columns(min(len(images), 2))
    for column, image in zip(columns, images):
        with column:
            st.image(image.image_url, width=150)
            label = f"[{image.title}]({image.source_url})" if image.source_url else image.title
            st.caption(f"위키백과 {image.kind} · {label}")


def render_collection_audit(result: AnswerResult) -> None:
    if not result.collection_audit:
        return
    with st.expander("외부 문서 수집·선별 이력"):
        for audit in result.collection_audit:
            cache = (
                "질문·문서 캐시 사용"
                if audit.get("question_cache_hit")
                else ("문서 캐시 사용" if audit.get("cache_hit") else "새 수집")
            )
            st.markdown(f"**검색어:** `{audit.get('query', '')}` · {cache}")
            st.write("색인 선택:", ", ".join(audit.get("selected", [])) or "없음")
            st.write("제외:", ", ".join(audit.get("discarded", [])) or "없음")


def ask_and_render(service: EPLService, item: EPLItem, question: str) -> None:
    with st.status("근거 문서를 수집하고 답변을 생성하는 중입니다…", expanded=True) as status:
        st.write("검색어 추출 및 위키백과 후보 검색")
        result = service.ask(item, question)
        st.write(f"외부 문서 {result.collected_document_count}건 수집/캐시 확인")
        st.write("LangGraph retrieve → generate 완료")
        status.update(label="답변 생성 완료", state="complete", expanded=False)
    st.session_state.histories.setdefault(item.item_id, []).append({"question": question, "result": result})


def select_item(item_id: str) -> None:
    st.session_state.selected_item_id = item_id


def render_selected_context(item: EPLItem) -> None:
    label = item_type_label(item.item_type)
    st.markdown(
        f"""
        <div class="context-card">
          <span class="context-card__badge">{html.escape(label)}</span>
          <div>
            <div class="context-card__title">{html.escape(item.title)}</div>
            <div class="context-card__text">{html.escape(item.text)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_background_music() -> None:
    with st.sidebar.expander("🎵 경기장 배경음악", expanded=False):
        st.caption("프로젝트 전용 오리지널 스타디움 루프 · 공식 EPL 테마곡 아님")
        if STADIUM_LOOP_FILE.exists():
            st.audio(str(STADIUM_LOOP_FILE), format="audio/wav", loop=True)
            st.caption("재생 버튼을 누른 뒤 플레이어에서 볼륨을 조절하세요.")
        else:
            st.caption("배경음악 파일을 준비 중입니다.")


settings = get_settings()
items, items_by_id, type_counts = load_catalog()
item_index_count = collection_count(settings, ITEM_COLLECTION)
item_index_current = is_item_index_current(settings, len(items))
auto_index_error: str | None = None
if settings.has_api_key and not item_index_current:
    with st.spinner(f"로컬 EPL 데이터 {len(items)}개를 자동 색인·갱신하는 중입니다…"):
        try:
            _, item_index_count = index_items(settings)
            item_index_current = is_item_index_current(settings, len(items))
        except Exception:
            # Do not expose an API trace or credential details to users.
            auto_index_error = "자동 색인에 실패했습니다. GMS_KEY, GMS_BASE_URL, 모델 권한과 네트워크 연결을 확인해 주세요."
st.session_state.setdefault("histories", {})
st.session_state.setdefault("selected_item_id", items[0].item_id)

with st.sidebar:
    st.markdown(
        """
        <div class="epl-brand">
          <div class="epl-brand__mark">⚽ EPL INSIGHT</div>
          <div class="epl-brand__name">기록 탐색 라운지</div>
          <div class="epl-brand__sub">2000-01~2025-26 완료 시즌<br>2026-27 수집 시점 스냅샷</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    metric_left, metric_right = st.columns(2)
    metric_left.metric("로컬 항목", len(items))
    metric_right.metric("색인 항목", item_index_count)
    if not settings.has_api_key:
        st.warning("`.env`에 `GMS_KEY`를 설정하면 색인과 RAG를 사용할 수 있습니다.")
    elif item_index_current:
        st.success("로컬 EPL 데이터 색인이 준비되었습니다.")
    if auto_index_error:
        st.error(auto_index_error)
    if settings.has_api_key and not item_index_current:
        st.info("Vector DB가 비어 있습니다. 앱을 새로고침하면 자동 색인을 다시 시도합니다.")
    render_background_music()
    st.divider()
    st.subheader("질문할 EPL 항목")
    type_options = ["전체", *sorted(type_counts)]
    selected_type = st.selectbox(
        "항목 유형",
        type_options,
        format_func=lambda item_type: "전체" if item_type == "전체" else item_type_label(item_type),
    )
    visible_items = items if selected_type == "전체" else [item for item in items if item.item_type == selected_type]
    if st.session_state.selected_item_id not in {item.item_id for item in visible_items}:
        st.session_state.selected_item_id = visible_items[0].item_id
    selected_id = st.selectbox(
        "질문할 EPL 항목 선택",
        options=[item.item_id for item in visible_items],
        format_func=lambda item_id: item_label(items_by_id[item_id]),
        key="selected_item_id",
    )

selected_item = items_by_id[selected_id]
st.markdown(
    """
    <section class="hero">
      <div class="hero__eyebrow">EVIDENCE-FIRST EPL KNOWLEDGE</div>
      <h1>프리미어리그, 기록으로 답하다</h1>
      <p>로컬 EPL 데이터와 위키백과 문서를 함께 확인해 근거 중심으로 답변합니다.</p>
    </section>
    """,
    unsafe_allow_html=True,
)
render_selected_context(selected_item)

with st.expander("자연어 조건으로 EPL 항목 찾기"):
    condition = st.text_input("예: 2000년대에 우승한 팀, EPL 득점왕을 받은 한국 선수")
    if st.button("조건으로 찾기") and condition:
        if not settings.has_api_key:
            st.error("먼저 GMS_KEY를 설정해 주세요.")
        elif not item_index_current:
            st.error("로컬 EPL 데이터 색인이 아직 준비되지 않았습니다. 잠시 후 새로고침해 주세요.")
        else:
            try:
                matches = get_service().find_by_condition(condition, items_by_id)
                if not matches:
                    st.warning("조건에 맞는 항목을 찾지 못했습니다.")
                for match in matches:
                    st.button(
                        item_label(match),
                        key=f"condition_{match.item_id}",
                        on_click=select_item,
                        args=(match.item_id,),
                    )
            except Exception:
                st.error("조건 탐색 중 문제가 발생했습니다. API 키와 로컬 색인 상태를 확인해 주세요.")

tab_chat, tab_compare = st.tabs(["질의응답", "EPL 기록 비교"])
with tab_chat:
    history = st.session_state.histories.get(selected_item.item_id, [])
    if not history:
        st.caption("선택 항목별 대화는 분리되어 저장됩니다. 아래 입력창에서 바로 질문해 보세요.")
    for turn in history:
        with st.chat_message("user"):
            st.write(turn["question"])
        with st.chat_message("assistant"):
            st.markdown(compact_answer_markdown(turn["result"].answer))
            render_profile_images(turn["result"].profile_images)
            render_evidence(turn["result"])
            render_collection_audit(turn["result"])
with tab_compare:
    st.caption("두 기록의 시즌·소속·선정·세부 기록을 근거와 함께 비교합니다.")
    comparison_ids = [item.item_id for item in items]
    left_column, right_column = st.columns(2)
    with left_column:
        st.markdown("**비교 대상 A**")
        left_id = st.selectbox("비교 대상 A 선택", comparison_ids, format_func=lambda item_id: item_label(items_by_id[item_id]), key="compare_left", label_visibility="collapsed")
    with right_column:
        st.markdown("**비교 대상 B**")
        right_id = st.selectbox("비교 대상 B 선택", comparison_ids, index=min(1, len(comparison_ids) - 1), format_func=lambda item_id: item_label(items_by_id[item_id]), key="compare_right", label_visibility="collapsed")
    comparison_question = st.text_input("비교 질문", "두 기록의 성과 차이를 근거와 함께 비교해줘.")
    if st.button("근거 기반 비교 생성"):
        if left_id == right_id:
            st.warning("서로 다른 두 항목을 선택해 주세요.")
        elif not settings.has_api_key:
            st.error("먼저 GMS_KEY를 설정해 주세요.")
        elif not item_index_current:
            st.error("로컬 EPL 데이터 색인이 아직 준비되지 않았습니다. 잠시 후 새로고침해 주세요.")
        else:
            try:
                with st.status("두 항목의 근거를 수집하고 비교하는 중입니다…", expanded=False) as status:
                    result = get_service().compare(items_by_id[left_id], items_by_id[right_id], comparison_question)
                    status.update(label="비교 리포트 생성 완료", state="complete")
                st.markdown(compact_answer_markdown(result.answer))
                render_profile_images(result.profile_images)
                render_evidence(result)
                render_collection_audit(result)
            except Exception:
                st.error("비교 처리 중 문제가 발생했습니다. API 키, 인터넷 연결, 색인 상태를 확인해 주세요.")


# A top-level chat input is pinned to the bottom of the Streamlit page, unlike
# an input nested inside a tab, which keeps the interaction close to a normal
# chatbot regardless of the selected item or the length of the conversation.
question = st.chat_input(f"{selected_item.title}에 관해 질문하세요")
if question:
    if not settings.has_api_key:
        st.error("`.env`에 GMS_KEY를 설정한 뒤 다시 시도해 주세요.")
    elif not item_index_current:
        st.error("로컬 EPL 데이터 색인이 아직 준비되지 않았습니다. 잠시 후 새로고침해 주세요.")
    else:
        try:
            ask_and_render(get_service(), selected_item, question)
            st.rerun()
        except Exception:
            st.error("답변 처리 중 문제가 발생했습니다. API 키, 인터넷 연결, 색인 상태를 확인해 주세요.")
