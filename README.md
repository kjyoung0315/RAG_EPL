# EPL Insight RAG

2000-01~2025-26 EPL 완료 시즌 기록과 2026-27 수집 시점 스냅샷을 활용하는 근거 기반 지식 서비스입니다. 로컬 JSON 메타데이터와 한국어 위키백과 문서를 분리한 두 ChromaDB 컬렉션으로 검색합니다.

## 필수 기능 대응

| 요구사항 | 구현 |
|---|---|
| F2001~F2002 | 837개 JSON을 읽어 711개 고유 EPL 항목으로 정규화하고 `epl_items`에 upsert |
| F2003~F2005 | LLM 검색어 추출, 위키백과 후보 선별, 캐시·청킹 후 `epl_external_docs` 색인 |
| F2006~F2008 | 선택 항목 근거 상시 포함, 외부 청크 검색·중복 제거, `[근거 N]` 및 원문 URL 표시 |
| F2009 | 항목별 분리 채팅 기록 |
| F2010 | 두 EPL 기록의 근거 기반 비교 리포트 |
| F2011 | 자연어 조건 → 벡터 후보 검색 → LLM 선별 → 항목 선택 |
| F2012 | 색인·수집·답변 진행 상태와 키 누락 안내 |

## 실행 방법

Python 3.10 이상이 필요합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 다음 값을 설정합니다. 프로젝트에서는 `GMS_KEY`를 우선 사용하며, 일반 OpenAI 키를 쓸 때만 `OPENAI_API_KEY`를 사용합니다.

```env
GMS_KEY=your_gms_key
GMS_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1/
WIKI_CONTACT=your.english.email@example.com
OPENAI_CHAT_MODEL=gpt-5.4-nano
```

로컬 데이터 구조를 확인합니다.

```powershell
python -m scripts.inspect_data
```

앱은 처음 실행할 때 로컬 항목 711개를 자동으로 색인합니다. 문서 형식이 바뀌면 저장된 색인을 한 번만 자동 갱신합니다. 선수는 `한글 이름 (영문 원문명)`으로 표시하며, 영문 원문도 함께 색인되어 두 언어 모두로 검색할 수 있습니다. 터미널에서 사전 색인이 필요할 때만 다음 명령을 사용합니다.

질문을 받으면 위키백과 API 문서를 먼저 수집·검색해 답변 근거의 앞부분에 배치합니다. 로컬 JSON은 위키 문서가 부족한 경우에만 보완 근거로 함께 사용합니다.

```powershell
python -m scripts.index_items
streamlit run app.py
```

## 데이터·출처 주의

- 모든 JSON 파일을 읽지만, 순위표·우승팀·매니페스트 등 같은 사실을 반복한 보조 파일은 벡터 중복을 막기 위해 검증용으로만 사용합니다.
- 과거 JSON의 일부 `text` 필드는 인코딩이 깨져 있으므로 구조화된 필드에서 검색 텍스트를 재생성합니다.
- 외부 문서는 한국어 위키백과 API에서 수집하며, 문서 제목·원문 URL·검색어를 청크 메타데이터로 보존합니다.
- 동일 항목에 동일한 질문을 다시 하면 질문별 검색어와 문서 결과를 모두 캐시해, 두 번째 실행에서는 새 위키백과 검색을 하지 않습니다. 앱의 `외부 문서 수집·선별 이력`에서 `질문·문서 캐시 사용`으로 확인할 수 있습니다.
- 2026-27 데이터는 진행 중 시즌의 수집 시점 스냅샷으로 취급합니다.
