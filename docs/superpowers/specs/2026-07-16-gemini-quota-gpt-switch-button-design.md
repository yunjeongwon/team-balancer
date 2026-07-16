# Gemini 할당량 초과 시 GPT 전환 버튼 설계

## 배경

현재 `app/llm/model.py`의 `get_model()`은 Gemini 기본 / `USE_GPT=1` 시 GPT를 반환하며, 할당량 초과 시 자동 전환은 없다(수동 env 스위치만). Gemini 무료티어 하루 할당량 초과(429 / `RESOURCE_EXHAUSTED`)가 발생하면 생성 흐름이 예외로 즉시 멈추고, 운영자가 `USE_GPT=1`을 주고 앱을 재시작해야 한다.

자동 폴백(langchain `with_fallbacks` + 콜백 플래그)도 검토했으나 기각:
- 할당량 예외 클래스를 정확히 매칭해야 동작(틀리면 **조용히 폴백 미동작**)
- 래퍼 클래스·콜백·플래그 등 부품이 많음
- 하루 할당량 초과 시 매 호출마다 Gemini 실패 호출을 반복
- "운영 가시성" 이슈(이전 설계에서 자동 폴백을 뺀 이유)를 근본적으로 해결하지 못함

대신 **에러 발생 시 사용자가 원클릭으로 GPT로 전환·재시도하는 버튼**을 제공한다. 명시적 사용자 행위이므로 가시성 문제가 해소되고, 한 번 전환하면 세션에 고정되어 반복 실패 호출도 없다.

## 결정 사항

- **에러 시 전환 버튼**: 최초 생성 흐름에서 `ValidationError`가 아닌 예외 발생 시 "GPT로 전환하고 재시도" 버튼 노출.
- **수동 env 스위치 유지**: `USE_GPT=1`은 시작부터 GPT 강제 오버라이드로 동작(기존 결정 유지). 버튼은 세션 도중 전환을 담당.
- **예외 분류 안 함**: 어떤 예외든(할당량/네트워크/기타 provider 오류) 전환 버튼을 보여준다. 할당량 예외 클래스 정확 매칭이라는 불확실성을 회피. 단 `ValidationError`는 입력 문제이므로 버튼 미노출(기존 안내 유지).
- **전환은 세션에 고정**: 한 번 전환하면 `st.session_state.use_gpt=True`로 세션 종료까지 GPT 유지. 할당량이 닳은 날 매 호출마다 Gemini 실패를 반복하지 않는다(자동 폴백 대비 장점).
- **자동 재시도**: 전환 버튼 클릭 시 모델 전환 + 입력(text area에 남아있음)으로 재생성까지 한 번에 수행. "에러 → 전환 → 팀 생성 다시 클릭"의 2단계 마찰 제거.
- **범위: 최초 생성 흐름만**: 피드백(resume) 흐름의 예외는 기존 generic 에러 처리 유지. 할당량은 보통 첫 생성에서 발견되며, 그 시점에 전환하면 이후 피드백 흐름도 이미 GPT로 동작.

## 변경 파일

1. **`app/llm/model.py`** — `get_model(use_gpt: bool)`. `@lru_cache` 유지(이제 `use_gpt`별로 캐시 → Gemini/GPT 각각 1개씩만 생성, 정확).
   ```python
   @lru_cache
   def get_model(use_gpt: bool):
       if use_gpt:
           return init_chat_model(model="gpt-5-mini", model_provider="openai")
       return init_chat_model(model="gemini-3.1-flash-lite", model_provider="google_genai")
   ```
2. **`app/graph/builder.py`** — `graph_builder(use_gpt: bool)` → `get_model(use_gpt)` 호출. 그래프 빌드 로직 자체는 변경 없음.
3. **`app/main.py`** —
   - `get_app(graph_code_stamp, use_gpt)`: 캐시 키에 `use_gpt` 추가. 전환 시 자동으로 GPT 그래프 빌드(`st.cache_resource.clear()` 불필요).
   - `app = get_app(graph_code_stamp(), _use_gpt())` where
     `_use_gpt() = os.environ.get("USE_GPT") == "1" or st.session_state.get("use_gpt", False)`.
   - 최초 생성 흐름의 `except Exception`: 기존 `st.error` + `st.exception`을 `st.error("Gemini 사용량 한도 등 오류가 발생했습니다. GPT로 전환해 다시 시도해보세요.")` + `st.button("GPT로 전환하고 재시도")`로 변경. 클릭 시 `session_state.use_gpt=True`, `session_state.pending_generate=True`, `st.rerun()`.
   - `pending_generate`가 설정된 경우(전환 직후 재실행) 팀 생성 로직을 자동 수행 후 플래그 해제.
4. **`tests/conftest.py`** — fixture 람다를 `lambda use_gpt: llm`로 변경(1줄). `RecordingFakeLLM` 자체는 변경 없음(`.with_structured_output(schema)` 계약 동일).
5. **`README.md`** — 환경변수/스위치 안내 갱신: `USE_GPT=1`(시작부터 강제) + 앱 내 전환 버튼(할당량 초과 에러 시).

## 환경변수

- `GOOGLE_API_KEY`(Gemini 기본), `OPENAI_API_KEY`(GPT) — langchain이 env에서 자동 읽음(기존과 동일).
- `USE_GPT=1` — 시작부터 GPT 강제(선택).
- `st.session_state.use_gpt` — 버튼으로 세션 도중 설정(런타임, 영구저장 아님).

## 테스트

- fixture 1줄 변경 후 `uv run pytest` 전체 통과 검증.
- `RecordingFakeLLM`이 `.with_structured_output(schema)` 계약을 그대로 만족하므로 그래프 빌드/생성 로직 테스트는 영향 없음.
- (선택) `get_model(use_gpt=True/False)`가 각각 openai/google_genai provider를 반환하는지 단위 테스트. 실제 API 호출은 하지 않음.

## Out of scope

- 자동 폴백 / 재시도 / 예외 분기(`with_fallbacks`, 콜백, 플래그) — 복잡도·가시성 이유로 미도입.
- 피드백(resume) 흐름의 전환 버튼 — 최초 생성에서 전환하면 충분하므로.
- 컨텍스트 윈도우 초과(입력이 너무 긴) 처리 — 근본 원인(프롬프트 길이)을 가릴 수 있어 별도.
- 전환 상태의 파일 영속화 — 세션 단위면 충분(재시작 시 env `USE_GPT`로 통제).
