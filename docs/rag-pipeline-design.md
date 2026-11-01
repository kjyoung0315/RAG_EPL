# EPL Insight RAG 파이프라인 설계서

## 컬렉션

| 컬렉션 | 용도 | 주요 메타데이터 |
|---|---|---|
| `epl_items` | 로컬 EPL JSON의 정규화 항목 | `item_id`, `item_type`, `title`, `season`, `team`, `source_url` |
| `epl_external_docs` | 위키백과 본문 청크 | `chunk_id`, `document_id`, `related_item_id`, `document_title`, `source_url`, `search_query` |

`team:{season}:{team}`, `pfa:{season}:{player}` 등 고정 ID로 upsert하여 재색인 시 중복 저장을 방지한다.

## 흐름

```text
로컬 JSON → 유형 분류·검색 텍스트 재구성 → epl_items upsert
선택 항목 + 질문 → 검색어 추출 → 위키 후보 검색 → 후보 선별 → 본문 수집·캐시
→ 청킹 → epl_external_docs upsert
→ retrieve(로컬 항목 1건 + 외부 Top-k) → 중복 제거·근거 번호 부여
→ generate(근거만 이용) → 답변 및 인용 문서 표시
```

## 설정값

| 설정 | 초기값 | 이유 |
|---|---:|---|
| `CHUNK_SIZE` | 1000 | 위키백과 문단 맥락을 보존하면서 검색 단위를 과도하게 키우지 않음 |
| `CHUNK_OVERLAP` | 200 | 문단 경계에서 문맥이 끊기는 문제 완화 |
| `RETRIEVAL_TOP_K` | 5 | 로컬 필수 근거 1건과 보완 외부 근거를 함께 제공 |
| `WIKI_REQUESTS_PER_MINUTE` | 10 | 연락처가 없을 때에도 보수적인 호출량 유지 |

## 프롬프트 역할

1. **검색어 추출:** 선택 항목 자체를 포함한 위키 검색어를 JSON으로 반환한다.
2. **후보 선별:** 후보 제목·요약 중 색인할 문서 번호만 JSON으로 반환한다.
3. **답변 생성:** 제공된 근거만 사용하고 주요 주장에 `[근거 N]`을 붙인다.

## 검증 방법

- `python -m scripts.inspect_data`로 원본 817개와 정규화 항목 691개를 확인한다.
- `python -m scripts.index_items`를 두 번 실행하고 컬렉션 건수가 증가하지 않는지 확인한다.
- 앱의 수집·선별 이력에서 선택 및 제외 문서를 확인한다.
- `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RETRIEVAL_TOP_K`를 `.env`에서 변경해 근거 목록 차이를 캡처한다.
