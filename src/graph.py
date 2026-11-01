from __future__ import annotations

from typing import NotRequired

from typing_extensions import TypedDict
from langgraph.graph import END, START, StateGraph

from src.llm import LLMService
from src.models import EPLItem, Evidence
from src.retriever import EPLRetriever


class RAGState(TypedDict):
    item: EPLItem
    question: str
    evidence: NotRequired[list[Evidence]]
    answer: NotRequired[str]


def build_rag_graph(retriever: EPLRetriever, llm: LLMService):
    def retrieve(state: RAGState) -> dict[str, list[Evidence]]:
        return {"evidence": retriever.retrieve(state["item"], state["question"])}

    def generate(state: RAGState) -> dict[str, str]:
        return {"answer": llm.answer(state["question"], state["evidence"])}

    graph = StateGraph(RAGState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
