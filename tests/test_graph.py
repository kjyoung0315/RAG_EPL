from src.graph import build_rag_graph
from src.models import EPLItem, Evidence


class FakeRetriever:
    def retrieve(self, item: EPLItem, question: str) -> list[Evidence]:
        return [Evidence(1, item.text, item.title, "", "EPL 로컬 JSON", item.item_id)]


class FakeLLM:
    def answer(self, question: str, evidence: list[Evidence]) -> str:
        return f"테스트 답변 [근거 {evidence[0].label}]"


def test_langgraph_uses_retrieve_then_generate() -> None:
    item = EPLItem("season:2000-01", "season_summary", "2000-01", "우승팀은 Manchester United다.", {})
    graph = build_rag_graph(FakeRetriever(), FakeLLM())
    result = graph.invoke({"item": item, "question": "우승팀은?"})
    assert result["answer"] == "테스트 답변 [근거 1]"
    assert result["evidence"][0].title == "2000-01"
