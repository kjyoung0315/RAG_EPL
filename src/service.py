from __future__ import annotations

from dataclasses import dataclass

from src.collector import WikipediaCollector
from src.config import Settings
from src.data_loader import load_items
from src.graph import build_rag_graph
from src.indexer import ITEM_COLLECTION, get_store
from src.llm import LLMService
from src.models import EPLItem, Evidence, ProfileImage
from src.player_records import player_record_summary, record_summary_markdown
from src.retriever import EPLRetriever


@dataclass
class AnswerResult:
    answer: str
    evidence: list[Evidence]
    collected_document_count: int
    collection_audit: list[dict[str, object]]
    profile_images: list[ProfileImage]


class EPLService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = LLMService(settings)
        self.collector = WikipediaCollector(settings, self.llm)
        self.catalog, _ = load_items(settings.data_dir)
        self.retriever = EPLRetriever(settings, self.catalog)
        self.graph = build_rag_graph(self.retriever, self.llm)
        self.item_store = get_store(settings, ITEM_COLLECTION)

    def ask(self, item: EPLItem, question: str) -> AnswerResult:
        documents = self.collector.collect_for_question(item, question)
        state = self.graph.invoke({"item": item, "question": question})
        return AnswerResult(
            answer=state["answer"],
            evidence=state["evidence"],
            collected_document_count=len(documents),
            collection_audit=list(self.collector.last_audits),
            profile_images=[image for image in [self.collector.profile_image(item)] if image is not None],
        )

    def find_by_condition(self, condition: str, items_by_id: dict[str, EPLItem], limit: int = 20) -> list[EPLItem]:
        documents = self.item_store.similarity_search(condition, k=limit)
        candidates = [items_by_id[doc.metadata["item_id"]] for doc in documents if doc.metadata.get("item_id") in items_by_id]
        allowed_ids = self.llm.filter_item_ids(condition, candidates)
        return [items_by_id[item_id] for item_id in allowed_ids]

    def compare(self, left: EPLItem, right: EPLItem, question: str) -> AnswerResult:
        """Domain-specific feature: compare two selected EPL records with cited evidence."""
        research_question = (
            f"{question}\n"
            "각 비교 대상 선수의 포지션, EPL 소속 이력, 주요 커리어 맥락도 함께 설명할 수 있도록 "
            "선수 소개 근거를 수집한다."
        )
        left_documents = self.collector.collect_for_question(left, research_question)
        left_audit = list(self.collector.last_audits)
        right_documents = self.collector.collect_for_question(right, research_question)
        right_audit = list(self.collector.last_audits)
        raw_evidence = self.retriever.retrieve(left, question) + self.retriever.retrieve(right, question)
        record_summaries = [
            summary
            for summary in (player_record_summary(left, self.catalog), player_record_summary(right, self.catalog))
            if summary is not None
        ]
        evidence: list[Evidence] = []
        seen: set[str] = set()
        for entry in [*raw_evidence, *record_summaries]:
            fingerprint = f"{entry.source_url}|{entry.text[:180]}"
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            evidence.append(Evidence(len(evidence) + 1, entry.text, entry.title, entry.source_url, entry.source_type, entry.item_id))
        generated_answer = self.llm.compare_answer(left, right, question, evidence)
        # Local player figures should never disappear merely because the model
        # focuses on the selected award record.
        summary = record_summary_markdown(evidence)
        answer = f"{summary}\n\n{generated_answer}" if summary else generated_answer
        return AnswerResult(
            answer=answer,
            evidence=evidence,
            collected_document_count=len(left_documents) + len(right_documents),
            collection_audit=left_audit + right_audit,
            profile_images=[
                image
                for image in (self.collector.profile_image(left), self.collector.profile_image(right))
                if image is not None
            ],
        )
