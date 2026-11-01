from __future__ import annotations

import json
import re
from typing import Any

from langchain_openai import ChatOpenAI

from src.config import Settings
from src.models import EPLItem, Evidence
from src.prompts import ANSWER_PROMPT, CANDIDATE_SELECTION_PROMPT, COMPARE_ANSWER_PROMPT, CONDITION_FILTER_PROMPT, QUERY_EXTRACTION_PROMPT


class LLMService:
    def __init__(self, settings: Settings) -> None:
        if not settings.has_api_key:
            raise RuntimeError("GMS_KEY is missing. Add it to .env before using RAG.")
        self.model = ChatOpenAI(
            model=settings.chat_model,
            temperature=0,
            api_key=settings.api_key,
            base_url=settings.api_base_url,
        )

    def _text(self, response: Any) -> str:
        content = response.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        return str(content)

    def invoke(self, prompt: str) -> str:
        return self._text(self.model.invoke(prompt)).strip()

    @staticmethod
    def json_object(text: str) -> dict[str, Any]:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        candidate = fenced.group(1) if fenced else text
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end < start:
            raise ValueError("The model response did not contain a JSON object.")
        value = json.loads(candidate[start : end + 1])
        if not isinstance(value, dict):
            raise ValueError("The model response was not a JSON object.")
        return value

    def extract_queries(self, item: EPLItem, question: str) -> list[str]:
        fallback = f"{item.title} {item.metadata.get('season', '')} Premier League".strip()
        try:
            payload = self.json_object(self.invoke(QUERY_EXTRACTION_PROMPT.format(item_text=item.text, question=question)))
            values = payload.get("queries", []) + [payload.get("must_include_query", "")]
            queries = [str(value).strip() for value in values if str(value).strip()]
        except Exception:
            queries = []
        return list(dict.fromkeys([fallback, *queries]))[:3]

    def choose_candidate_indices(self, item: EPLItem, question: str, candidates: list[dict[str, str]]) -> list[int]:
        if not candidates:
            return []
        text = "\n".join(f"[{index}] {candidate['title']}: {candidate.get('snippet', '')}" for index, candidate in enumerate(candidates))
        try:
            payload = self.json_object(self.invoke(CANDIDATE_SELECTION_PROMPT.format(item_title=item.title, question=question, candidates=text)))
            indices = payload.get("selected_indices", [])
            return [int(index) for index in indices if isinstance(index, int) and 0 <= index < len(candidates)]
        except Exception:
            return list(range(min(2, len(candidates))))

    def filter_item_ids(self, condition: str, candidates: list[EPLItem]) -> list[str]:
        candidate_text = "\n".join(f"- {item.item_id}: {item.text}" for item in candidates)
        try:
            payload = self.json_object(self.invoke(CONDITION_FILTER_PROMPT.format(condition=condition, candidates=candidate_text)))
            allowed = {item.item_id for item in candidates}
            return [item_id for item_id in payload.get("item_ids", []) if item_id in allowed]
        except Exception:
            return [item.item_id for item in candidates]

    def answer(self, question: str, evidence: list[Evidence]) -> str:
        evidence_text = "\n\n".join(
            f"[근거 {entry.label}] ({entry.source_type}) {entry.title}\n{entry.text}"
            for entry in evidence
        )
        try:
            return self.invoke(ANSWER_PROMPT.format(question=question, evidence=evidence_text))
        except Exception:
            return self._offline_evidence_answer(evidence)

    def compare_answer(self, left: EPLItem, right: EPLItem, question: str, evidence: list[Evidence]) -> str:
        evidence_text = "\n\n".join(
            f"[근거 {entry.label}] 비교 대상 {entry.item_id} · ({entry.source_type}) {entry.title}\n{entry.text}"
            for entry in evidence
        )
        try:
            return self.invoke(
                COMPARE_ANSWER_PROMPT.format(
                    question=question,
                    left_title=left.title,
                    left_id=left.item_id,
                    right_title=right.title,
                    right_id=right.item_id,
                    evidence=evidence_text,
                )
            )
        except Exception:
            return self._offline_evidence_answer(evidence)

    @staticmethod
    def _offline_evidence_answer(evidence: list[Evidence]) -> str:
        """Keep the UI useful when the text-generation gateway is temporarily unavailable."""
        if not evidence:
            return "현재 AI 응답 서버에 연결할 수 없고, 표시할 로컬 근거도 없습니다. 잠시 후 다시 시도해 주세요."
        lines = ["**AI 응답 서버 연결이 일시적으로 지연되고 있습니다. 아래 확인된 기록을 표시합니다.**"]
        lines.extend(f"- {entry.text} [근거 {entry.label}]" for entry in evidence)
        return "\n".join(lines)
