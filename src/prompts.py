QUERY_EXTRACTION_PROMPT = """당신은 EPL 역사와 기록을 다루는 리서처다.
선택 항목과 사용자 질문을 바탕으로 한국어 위키백과 검색에 쓸 검색어를 만든다.
선택 항목 자체를 설명하는 검색어는 반드시 포함한다. 사실을 만들지 말고 JSON만 출력한다.

선택 항목:
{item_text}

사용자 질문:
{question}

출력 형식:
{{"queries": ["검색어 1", "검색어 2"], "must_include_query": "선택 항목 검색어"}}
"""

CANDIDATE_SELECTION_PROMPT = """당신은 EPL 지식 서비스의 문서 선별기다.
아래 후보 중 선택 항목과 질문에 직접 근거가 되는 문서만 고른다.
선택 항목 자체를 다루는 후보가 있으면 반드시 선택한다. 번호는 0부터 시작한다.
JSON만 출력한다.

선택 항목: {item_title}
질문: {question}

후보:
{candidates}

출력 형식:
{{"selected_indices": [0, 2]}}
"""

ANSWER_PROMPT = """당신은 EPL 기록 기반 RAG 어시스턴트다.
반드시 아래 근거 안의 내용만 사용해 한국어로 답한다.
주요 문장마다 [근거 번호]를 붙인다. 근거에 없는 사실은 추측하지 말고
'제공된 문서에서 확인되지 않습니다'라고 답한다. 수치와 시즌은 특히 엄격하게 확인한다.

질문: {question}

근거:
{evidence}
"""

ANSWER_PROMPT += """

근거 우선순위:
- `위키백과 API`로 수집된 외부 문서를 먼저 사용해 답한다.
- 외부 문서가 질문을 뒷받침하지 못하거나 누락된 경우에만 `EPL 로컬 JSON (보완 근거)`을 사용한다.
- 둘의 내용이 다르면 위키백과 API 문서의 내용을 우선하고, 충돌 사실을 짧게 알린다.

답변 상세도와 형식:
- 한두 문장으로 끝내지 말고, 근거가 충분한 경우 최소 3개의 서로 다른 사실을 활용한다.
- `**핵심 답변**`, `**확인된 기록·배경**`, `**해석·한계**` 순서의 짧은 굵은 라벨을 사용한다. Markdown 제목(`#`)은 사용하지 않는다.
- 기록·배경에서는 질문과 관련된 시즌, 소속 팀, 포지션, 경기 수, 승점, 득점, 도움, 순위, 수상, 커리어 맥락 중 근거에 있는 정보를 가능한 한 구체적으로 설명한다.
- 질문이 현재 팀 선수단·명단·스쿼드에 관한 것이고 `EPL 로컬 JSON (현재 선수단)` 근거가 있으면, 그 근거에 포함된 선수를 한 명도 빼지 말고 이름·포지션·등번호를 글머리표로 나열한다. 이때 스냅샷의 전체 명단 여부와 기준일도 함께 밝힌다.
- 같은 사실을 반복하지 말고, 서로 다른 근거가 있으면 각각의 정보를 자연스럽게 연결한다.
"""

COMPARE_ANSWER_PROMPT = """You are an EPL record comparison assistant. Answer in Korean using only the evidence below.
The selected comparison targets are fixed: A is {left_title} (ID: {left_id}) and B is {right_title} (ID: {right_id}).
Do not replace either target with a person merely mentioned in evidence. Do not say the targets are ambiguous.

Write a useful, substantive comparison in this exact order. Use bold inline labels such as `**A · 선수 정보와 기록**`; never use Markdown headings (`#`, `##`, etc.). Keep every label to one short line.
1. `A · 선수 정보와 기록`: explain the player's documented position, club/career context, or notable career achievement when present in A's evidence. Include any local record-summary figures (PFA selection count, appearances, goals or assists) supplied for A, then explain the selected EPL record.
2. `B · 선수 정보와 기록`: do the same using only B's evidence.
3. `기록 비교`: compare the selected records directly (season, club, position, award and any comparable performance information).

For each player, include two or more distinct career-context or record facts when that player's evidence provides them; do not limit the answer to the PFA selection line. When a local record-summary evidence item is supplied, it must be used in the answer. Describe season, club, position, appearances, goals, assists, awards, and career context whenever the supplied evidence supports them. Never infer a superiority ranking if comparable statistics are absent. Cite every factual claim with its evidence number such as [근거 1]. If evidence does not support a claim, say it cannot be confirmed from the provided documents.

Question: {question}

Evidence:
{evidence}
"""

CONDITION_FILTER_PROMPT = """당신은 EPL 항목 탐색 결과를 선별한다.
사용자 조건을 만족하는 후보의 item_id만 JSON으로 반환한다. 후보에 없는 항목은 만들지 마라.

조건: {condition}
후보:
{candidates}

출력 형식: {{"item_ids": ["item_id"]}}
"""
