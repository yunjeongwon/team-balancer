# Gemini 할당량 초과 시 GPT 전환 버튼 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 최초 팀 생성 흐름에서 (ValidationError가 아닌) 예외 발생 시 "GPT로 전환하고 재시도" 버튼을 노출하고, 클릭하면 세션을 GPT로 전환해 자동 재생성한다.

**Architecture:** 모델 선택을 `get_model(use_gpt)`로 명시화하고 `graph_builder(use_gpt)`·`get_app(stamp, use_gpt)`로 스레드. `@st.cache_resource` 캐시 키에 `use_gpt`를 추가해, 전환 시 자동으로 GPT 그래프가 빌드되도록 한다(`cache_resource.clear()` 불필요). 전환 상태는 `st.session_state.use_gpt`(세션 고정), 재생성 트리거는 `session_state.pending_generate`(pop으로 1회 소비). 자동 폴백(`with_fallbacks`/콜백/예외 매칭)은 도입하지 않는다.

**Tech Stack:** Streamlit(langchain `@st.cache_resource`, `st.button`, `st.session_state`, `streamlit.testing.v1.AppTest`), LangGraph, langchain `init_chat_model`.

## Global Constraints

- 기본 Gemini 모델 문자열: `gemini-3.1-flash-lite`, provider `google_genai`. GPT 모델 문자열: `gpt-5-mini`, provider `openai`. (정확한 값, 변경 금지)
- `init_chat_model`은 env의 `GOOGLE_API_KEY`/`OPENAI_API_KEY`를 자동 읽음.
- `USE_GPT=1` env는 시작부터 GPT 강제 오버라이드(기존 동작 유지).
- UI 테스트는 `streamlit.testing.v1.AppTest` 사용. `RecordingFakeLLM` fixture가 `builder.get_model`을 monkeypatch한다.
- 테스트 실행: `uv run pytest`.
- 커밋 메시지: 한국어 + conventional-commits prefix. master에서 직접 작업.

## File Structure

- `app/llm/model.py` — `get_model(use_gpt)` 만 담당. provider 선택의 단일 출처.
- `app/graph/builder.py` — `graph_builder(use_gpt)`가 `get_model(use_gpt)` 호출. 빌드 로직 자체는 불변.
- `app/main.py` — `get_app(stamp, use_gpt)` 캐시 키, `_use_gpt()` 판정, 예외 시 전환 버튼 + `pending_generate` 자동 재생성.
- `tests/conftest.py` — fixture 람다 시그니처 1줄 변경.
- `tests/test_model.py`(신규) — `get_model(use_gpt)` provider 선택 단위 테스트.
- `tests/test_main_app.py` — 전환 버튼 렌더링 AppTest 추가.
- `README.md` — env/스위치 안내 갱신.

---

### Task 1: `get_model(use_gpt)` provider 선택

**Files:**
- Modify: `app/llm/model.py`
- Test: `tests/test_model.py` (Create)

**Interfaces:**
- Consumes: 없음.
- Produces: `get_model(use_gpt: bool = False) -> BaseChatModel`. `@lru_cache` 유지(인자별 캐시). `use_gpt=True` → `init_chat_model(model="gpt-5-mini", model_provider="openai")`, else → `init_chat_model(model="gemini-3.1-flash-lite", model_provider="google_genai")`.

- [ ] **Step 1: Write the failing test**

`tests/test_model.py`:
```python
from app.llm import model as model_mod


def _spy_init(monkeypatch, calls):
    def fake_init(model, model_provider):
        calls.append({"model": model, "model_provider": model_provider})
        return object()

    monkeypatch.setattr(model_mod, "init_chat_model", fake_init)


def test_get_model_uses_gemini_by_default(monkeypatch):
    calls = []
    _spy_init(monkeypatch, calls)
    model_mod.get_model.cache_clear()

    model_mod.get_model(use_gpt=False)

    assert calls[-1] == {"model": "gemini-3.1-flash-lite", "model_provider": "google_genai"}


def test_get_model_uses_gpt_when_use_gpt_true(monkeypatch):
    calls = []
    _spy_init(monkeypatch, calls)
    model_mod.get_model.cache_clear()

    model_mod.get_model(use_gpt=True)

    assert calls[-1] == {"model": "gpt-5-mini", "model_provider": "openai"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_model.py -v`
Expected: FAIL — `get_model()` takes 0 positional arguments but `use_gpt` given (현재 시그니처 불일치).

- [ ] **Step 3: Write minimal implementation**

`app/llm/model.py` 전체:
```python
import os
from functools import lru_cache
from langchain.chat_models import init_chat_model

@lru_cache
def get_model(use_gpt: bool = False):
    # 기본은 Gemini. USE_GPT=1 또는 세션 전환 시 GPT 사용.
    if use_gpt:
        return init_chat_model(model="gpt-5-mini", model_provider="openai")
    return init_chat_model(model="gemini-3.1-flash-lite", model_provider="google_genai")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_model.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/llm/model.py tests/test_model.py
git commit -m "feat(llm): get_model이 use_gpt 인자로 provider 선택"
```

---

### Task 2: `graph_builder(use_gpt)` 스레딩 + fixture 시그니처 정합

`graph_builder`가 `get_model(use_gpt)`를 호출하도록 바꾼다. `graph_builder()` 무인자 호출(test_graph_builder.py)이 깨지지 않도록 기본값 `use_gpt=False`를 둔다. fixture 람다도 인자를 받아야 같이 변경(한 셋에 적용하지 않으면 전체 AppTest/test_graph_builder가 깨짐).

**Files:**
- Modify: `app/graph/builder.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Consumes: Task 1의 `get_model(use_gpt)`.
- Produces: `graph_builder(use_gpt: bool = False)`. 기존 노드 구성/엣지는 불변.

- [ ] **Step 1: Apply both changes together**

`app/graph/builder.py` — 시그니처와 `get_model` 호출만 변경(13·16행 부근):
```python
def graph_builder(use_gpt: bool = False):
    builder = StateGraph(TeamState)

    llm = get_model(use_gpt)
```
(나머지 빌드 로직은 그대로.)

`tests/conftest.py` — fixture 람다에 `use_gpt` 인자 추가(51행):
```python
    monkeypatch.setattr(builder_mod, "get_model", lambda use_gpt: llm)
```

- [ ] **Step 2: Run existing graph + 전체 suite로 정합 확인**

Run: `uv run pytest tests/test_graph_builder.py -v`
Expected: PASS — `graph_builder()` 무인자 호출이 기본값으로 동작.

Run: `uv run pytest -q`
Expected: PASS — fixture 람다가 `get_model(use_gpt)` 호출을 받음, 기존 AppTest 포함 전체 통과.

- [ ] **Step 3: Commit**

```bash
git add app/graph/builder.py tests/conftest.py
git commit -m "refactor(graph): graph_builder가 use_gpt를 get_model로 전달"
```

---

### Task 3: main.py 전환 버튼 + 캐시 키 + 자동 재생성

`get_app` 캐시 키에 `use_gpt` 추가, `_use_gpt()` 판정(또는 강제 env), 예외 시 전환 버튼 렌더링. 클릭 시 `use_gpt`/`pending_generate` 세팅 후 `st.rerun()`.

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: Task 2의 `graph_builder(use_gpt)`.
- Produces: main.py UI 동작(버튼). 다른 모듈에서 참조 없음.

- [ ] **Step 1: Write the failing test**

`tests/test_main_app.py` 상단 import에 `import streamlit as st` 추가(이미 `from streamlit.testing.v1 import AppTest` 있음). 파일 끝에 테스트 추가:
```python
def test_switch_button_renders_on_generation_error(monkeypatch):
    class _RaisingBound:
        def invoke(self, prompt):
            raise RuntimeError("simulated quota exceeded")

    class _RaisingFakeLLM:
        def with_structured_output(self, schema):
            return _RaisingBound()

    st.cache_resource.clear()
    monkeypatch.setattr(builder_mod, "get_model", lambda use_gpt=False: _RaisingFakeLLM())

    at = AppTest.from_file("app/main.py")
    at.session_state["authenticated"] = True
    at.run()

    at.text_area[0].input("팀원:\na\nb\nc\nd\n").run()
    at.button[0].click().run()

    labels = [b.label for b in at.button]
    assert "GPT로 전환하고 재시도" in labels
```
(`builder_mod`를 참조하므로 `import app.graph.builder as builder_mod`도 파일 상단 import에 추가.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main_app.py::test_switch_button_renders_on_generation_error -v`
Expected: FAIL — 버튼 라벨에 "GPT로 전환하고 재시도" 없음(현재는 generic `st.error`/`st.exception`만).

- [ ] **Step 3: Implement main.py changes**

(a) `import os` 추가(1행 부근 import 블록).

(b) `get_app` 시그니처 + 호출부(16–18행과 68행):
```python
@st.cache_resource
def get_app(graph_code_stamp: tuple[tuple[str, int], ...], use_gpt: bool):
    return graph_builder(use_gpt)


def _use_gpt() -> bool:
    return os.environ.get("USE_GPT") == "1" or st.session_state.get("use_gpt", False)
```
호출부(68행):
```python
app = get_app(graph_code_stamp(), _use_gpt())
```

(c) 생성 트리거를 `pending_generate`로 일반화하고 예외 블록에 버튼 추가. `if team_create_button_clicked:`(103행)을 아래로 교체:
```python
should_generate = team_create_button_clicked or st.session_state.pop("pending_generate", False)

if should_generate:
    st.session_state.awaiting_approval = False
    st.session_state.config = None

    if not team_request_input.strip():
        st.warning("팀원을 입력해주세요.")
    else:
        msg = None
        try:
            parsed_request = parse_team_request(team_request_input)

            st.session_state.thread_id = str(uuid.uuid4())
            configure_run_logging(st.session_state.thread_id)

            st.session_state.messages.append({
                "role": "user",
                "content": team_request_input,
            })

            msg = st.info("팀 생성 중 ..")

            config = {
                "configurable": {
                    "thread_id": st.session_state.thread_id
                }
            }

            app.invoke(
                {
                    "members_input": parsed_request["members_input"],
                    "must_link_groups_input": parsed_request["must_link_groups_input"],
                    "cannot_link_groups_input": parsed_request["cannot_link_groups_input"],
                    "default_score": 4,
                },
                config=config,
            )

            snapshot = app.get_state(config)

            if snapshot.next:
                st.session_state.awaiting_approval = True
                st.session_state.config = config

                values = snapshot.values
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": build_team_message(values),
                })

            msg.empty()
        except ValidationError as e:
            if msg:
                msg.empty()
            st.error(str(e) + ". 입력을 수정한 후 다시 팀 생성 버튼을 눌러주세요.")
        except Exception as e:
            if msg:
                msg.empty()
            st.error("Gemini 사용량 한도 등 오류가 발생했습니다. GPT로 전환해 다시 시도해보세요.")
            if st.button("GPT로 전환하고 재시도"):
                st.session_state.use_gpt = True
                st.session_state.pending_generate = True
                st.rerun()
```
(위 블록은 기존 103–161행의 내용과 동일하되, (1) `if team_create_button_clicked:` → `should_generate`/`pop`, (2) 마지막 `except Exception` 두 줄을 `st.error` + 전환 버튼으로 교체.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main_app.py::test_switch_button_renders_on_generation_error -v`
Expected: PASS

- [ ] **Step 5: Run full suite for regression**

Run: `uv run pytest -q`
Expected: PASS — 기존 AppTest/그래프 테스트 회귀 없음.

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_main_app.py
git commit -m "feat(main): 할당량 초과 에러 시 GPT 전환 버튼 추가"
```

---

### Task 4: README 갱신

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update env/switch docs**

`README.md`의 환경변수/스위치 안내 섹션에 아래 내용 반영(기존 `USE_GPT`/provider key 설명이 있으면 그 자리에):
- `GOOGLE_API_KEY` — Gemini(기본)용.
- `OPENAI_API_KEY` — GPT 전환용.
- `USE_GPT=1` (선택) — 앱 시작부터 GPT 강제.
- 앱 내 전환 — 팀 생성 중 Gemini 오류(할당량 초과 등) 발생 시 "GPT로 전환하고 재시도" 버튼이 노출되며, 클릭 시 해당 세션에서 GPT로 전환 후 자동 재생성.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: GPT 전환 버튼 및 환경변수 안내 갱신"
```

---

### Task 5: 수동 검증(전환→재생성 정상 라운드트립)

AppTest는 버튼 렌더링까지만 커버. 클릭→GPT 전환→재생성 라운드트립과 일반 흐름 회귀는 수동으로 확인한다.

- [ ] **Step 1: 일반 흐름 회귀 확인**

Run: `uv run streamlit run app/main.py`
- 정상 입력으로 팀 생성 → Gemini로 정상 동작 확인(회귀 없음).
- 종료.

- [ ] **Step 2: 에러→전환 라운드트립 확인(할당량 에러 시뮬레이션)**

Gemini 호출이 실패하도록 `GOOGLE_API_KEY`를 일시적으로 잘못된 값으로 설정한 뒤 실행:
```bash
GOOGLE_API_KEY=invalid OPENAI_API_KEY=<실제키> uv run streamlit run app/main.py
```
- 팀 생성 → Gemini 에러 발생 → "GPT로 전환하고 재시도" 버튼 노출 확인.
- 버튼 클릭 → GPT로 전환되어 같은 입력으로 팀이 생성되는지 확인.
- 이후 같은 세션에서 추가 생성이 GPT로 동작하는지(세션 고정) 확인.
- 종료 후 원래 `GOOGLE_API_KEY` 복구.

(실제 무료티어 할당량 초과 상황에서도 동일하게 동작해야 함. 로컬에서는 위 시뮬레이션으로 대체.)

---

## Self-Review

- **Spec coverage:** (1) 에러 시 전환 버튼 → Task 3. (2) `USE_GPT` 강제 오버라이드 유지 → `_use_gpt()`(Task 3). (3) 예외 분류 안 함(ValidationError 제외) → Task 3의 `except ValidationError` 분기 유지 + `except Exception`에서 버튼. (4) 세션 고정 → `session_state.use_gpt`. (5) 자동 재시도 → `pending_generate`. (6) 범위 최초 생성 흐름 → main.py 생성 블록만 수정, feedback `except`(208행 부근)는 미변경. (7) `get_model(use_gpt)`·`graph_builder`·fixture → Task 1·2. (8) README → Task 4. 빠진 항목 없음.
- **Placeholder scan:** "적절히"·"TBD" 없음. 모든 코드 스텝에 실제 코드 포함.
- **Type consistency:** `get_model(use_gpt)`(Task 1) → `graph_builder`의 `get_model(use_gpt)`(Task 2) → fixture `lambda use_gpt: llm`(Task 2) → `get_app(stamp, use_gpt)`/`graph_builder(use_gpt)`(Task 3) 시그니처 일관. 버튼 라벨 "GPT로 전환하고 재시도"가 Task 3 구현과 테스트 양쪽에 동일 문자열로 사용.
