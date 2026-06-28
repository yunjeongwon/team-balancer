# Team Balancer 버그 수정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LangGraph 기반 팀 생성 워크플로우가 실제로 동작하도록 만들고(누락된 의존성), 두 번 이상 "팀 생성"을 클릭했을 때 이전 상태가 새 생성에 섞여 들어가는 문제와 그에 얽힌 부수 버그들(피드백 dict 오염, EMPTY 더미 노출, 평가 실패 사유 미반영, FAIL 상태 미노출, 입력 파싱 버그)을 고치고, 죽은 코드를 정리한다.

**Architecture:** 기존 5-노드 LangGraph(`input → score_fetch → team_generator → evaluator → human_approval`) 구조는 그대로 유지한다. 변경은 (1) 의존성 선언, (2) 개별 노드/유틸 함수의 버그 수정, (3) `app/main.py`의 Streamlit 세션-상태 관리 수정, (4) 죽은 코드 제거로 한정한다. 새로운 노드나 그래프 구조 변경은 없다.

**Tech Stack:** Python 3.14, LangGraph, LangChain, Streamlit, Pydantic, pytest(신규 추가), `streamlit.testing.v1.AppTest`(신규 사용).

## Global Constraints

- 실제 LLM API 키 없이도 전체 테스트가 통과해야 한다 — 모든 테스트는 `conftest.py`의 `RecordingFakeLLM`으로 `app.graph.builder.get_model`을 monkeypatch한다.
- 그래프의 5-노드 구조, `TeamState` 스키마의 기존 필드 의미는 유지한다 (죽은 필드 제거 제외).
- 모든 테스트는 `PYTHONPATH=. uv run pytest -q <경로>` 로 실행한다 (이 프로젝트는 `app` 패키지를 절대경로로 import하므로 README의 기존 실행 관례와 동일하게 `PYTHONPATH=.`가 필요하다).
- 각 태스크 종료 시 `git commit`.

---

### Task 1: 누락된 의존성 추가 + 테스트 인프라 구축

**문제:** `pyproject.toml`에 `langgraph`, `langchain`, `python-dotenv`가 선언되어 있지 않아 `uv run`/`uv sync` 환경에서 앱이 import 단계부터 `ModuleNotFoundError`로 죽는다. 동시에 이후 모든 태스크에서 쓸 가짜 LLM 테스트 인프라가 없다.

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `tests/test_graph_builder.py`

**Interfaces:**
- Produces: `tests/conftest.py`의 `fake_llm` fixture — `app.graph.builder.get_model`을 monkeypatch하여 `RecordingFakeLLM` 인스턴스를 반환한다. `RecordingFakeLLM`은 `.team_prompts: list`, `.eval_prompts: list`, `.team_responses: list[TeamSchema]`, `.eval_responses: list[EvaluationSchema]` 속성을 가진다. 이후 모든 태스크의 테스트가 이 fixture를 사용한다.

- [ ] **Step 1: pytest를 dev 의존성으로 추가**

```bash
uv add --dev pytest
```

- [ ] **Step 2: 실패하는 테스트(및 테스트 인프라) 작성**

`tests/conftest.py`:

```python
import pytest

from app.schemas.evaluation_schema import EvaluationSchema
from app.schemas.team_schema import TeamSchema


class _Bound:
    """invoke() 호출마다 받은 prompt를 기록하고, 미리 준비된 응답을
    순서대로 돌려준다. 응답 목록이 바닥나면 마지막 응답을 반복한다."""

    def __init__(self, log, responses):
        self.log = log
        self.responses = responses

    def invoke(self, prompt):
        self.log.append(prompt)
        index = min(len(self.log) - 1, len(self.responses) - 1)
        return self.responses[index]


class RecordingFakeLLM:
    """실제 LLM 대신 사용하는 stub. team_generator/evaluator 노드가
    받는 프롬프트를 기록해, API 키 없이 프롬프트 내용을 검증할 수 있게 한다."""

    def __init__(self):
        self.team_prompts = []
        self.eval_prompts = []
        self.team_responses = [
            TeamSchema(team_a=[], team_b=[], score_diff=0, reason="fake-team")
        ]
        self.eval_responses = [EvaluationSchema(status="PASS", reason="fake-pass")]

    def with_structured_output(self, schema):
        if schema is TeamSchema:
            return _Bound(self.team_prompts, self.team_responses)
        return _Bound(self.eval_prompts, self.eval_responses)


@pytest.fixture
def fake_llm(monkeypatch):
    import app.graph.builder as builder_mod

    llm = RecordingFakeLLM()
    monkeypatch.setattr(builder_mod, "get_model", lambda: llm)
    return llm
```

`tests/test_graph_builder.py`:

```python
import app.graph.builder as builder_mod


def test_graph_builder_compiles_with_expected_nodes(fake_llm):
    app = builder_mod.graph_builder()
    graph = app.get_graph()

    assert set(graph.nodes) == {
        "__start__",
        "__end__",
        "input",
        "score_fetch",
        "team_generator",
        "evaluator",
        "human_approval",
    }
```

- [ ] **Step 3: 테스트 실행 → ModuleNotFoundError로 실패 확인**

Run: `PYTHONPATH=. uv run pytest -q tests/test_graph_builder.py`
Expected: `ModuleNotFoundError: No module named 'langgraph'`로 실패

- [ ] **Step 4: 누락된 런타임 의존성 추가**

```bash
uv add langgraph langchain python-dotenv
```

- [ ] **Step 5: 테스트 재실행 → 통과 확인**

Run: `PYTHONPATH=. uv run pytest -q tests/test_graph_builder.py`
Expected: `1 passed`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock tests/conftest.py tests/test_graph_builder.py
git commit -m "fix: add missing langgraph/langchain/python-dotenv deps, add test infra"
```

---

### Task 2: input_node 공백 파싱 버그 수정

**문제:** [app/graph/nodes/input_node.py:11](app/graph/nodes/input_node.py#L11)에서 `members_input.split(" ")`을 쓰기 때문에, 사용자가 공백을 두 번 입력하면(`"a  b c"`) 빈 문자열이 멤버로 들어간다(`['a', '', 'b', 'c']`). `.split()`(인자 없음)은 연속 공백을 하나로 처리하므로 이 문제가 사라진다.

**Files:**
- Modify: `app/graph/nodes/input_node.py:11`
- Test: `tests/test_input_node.py`

**Interfaces:**
- Consumes: 없음 (순수 함수 `input_node(state: TeamState) -> TeamState`, 변경 없음)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_input_node.py`:

```python
import pytest

from app.exceptions.validation import ValidationError
from app.graph.nodes.input_node import input_node


def _state(members_input, must_link="", cannot_link=""):
    return {
        "members_input": members_input,
        "must_link_groups_input": must_link,
        "cannot_link_groups_input": cannot_link,
    }


def test_collapses_repeated_spaces_instead_of_creating_blank_member():
    result = input_node(_state("a  b c"))

    assert "" not in result["members"]
    assert result["members"] == ["a", "b", "c", "EMPTY"]


def test_even_member_count_is_not_padded():
    result = input_node(_state("a b c d"))

    assert result["members"] == ["a", "b", "c", "d"]


def test_rejects_duplicate_members():
    with pytest.raises(ValidationError):
        input_node(_state("a a b"))


def test_must_link_group_with_unknown_member_is_rejected():
    with pytest.raises(ValidationError):
        input_node(_state("a b c", must_link="a-z"))
```

- [ ] **Step 2: 테스트 실행 → 첫 번째 테스트 실패 확인**

Run: `PYTHONPATH=. uv run pytest -q tests/test_input_node.py`
Expected: `test_collapses_repeated_spaces_instead_of_creating_blank_member` FAIL
(`result["members"] == ['a', '', 'b', 'c', 'EMPTY']`가 되어 assert 실패. 나머지 3개는 이미 PASS.)

- [ ] **Step 3: 최소 수정**

`app/graph/nodes/input_node.py:11`을 수정:

```python
    # members_input => members
    members = members_input.split()
```

(기존 `members = members_input.split(" ")`를 위 코드로 교체)

- [ ] **Step 4: 테스트 재실행 → 전체 통과 확인**

Run: `PYTHONPATH=. uv run pytest -q tests/test_input_node.py`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add app/graph/nodes/input_node.py tests/test_input_node.py
git commit -m "fix: collapse repeated whitespace in member input instead of creating blank members"
```

---

### Task 3: evaluator의 FAIL 사유를 team_generator 재시도 프롬프트에 반영

**문제:** [app/graph/builder.py:31-38](app/graph/builder.py#L31-L38)의 `evaluator_continue`는 평가가 FAIL이면 `team_generator`로 돌아가 자동 재시도하지만, [app/utils/build_team_generator_base_prompt_section.py](app/utils/build_team_generator_base_prompt_section.py)의 `feedback_section`은 사람 피드백(`feedback`)이 있을 때만 추가되고 evaluator의 `evaluation_reason`은 어디서도 재생성 프롬프트에 전달되지 않는다. 자동 재시도가 "뭐가 잘못됐는지 모른 채 다시 뽑기"가 되어 비효율적이다.

**Files:**
- Modify: `app/utils/build_team_generator_base_prompt_section.py`
- Modify: `app/graph/nodes/team_generator_node.py`
- Test: `tests/test_team_generator_node.py`

**Interfaces:**
- Produces: `build_team_generator_prompt(score_groups, must_link_groups, cannot_link_groups, feedback, team_a, team_b, evaluation_reason=None)` — 새 키워드 인자 `evaluation_reason` 추가(기본값 `None`, 하위호환).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_team_generator_node.py`:

```python
from app.schemas.evaluation_schema import EvaluationSchema
from app.schemas.team_schema import TeamSchema
import app.graph.builder as builder_mod


def test_fail_reason_is_fed_back_into_the_retry_prompt(fake_llm):
    fake_llm.eval_responses = [
        EvaluationSchema(status="FAIL", reason="must_link 위반: a, b가 다른 팀"),
        EvaluationSchema(status="PASS", reason="ok"),
    ]
    fake_llm.team_responses = [
        TeamSchema(team_a=["a"], team_b=["b"], score_diff=0, reason="try-1"),
        TeamSchema(team_a=["b"], team_b=["a"], score_diff=0, reason="try-2"),
    ]

    app = builder_mod.graph_builder()
    config = {"configurable": {"thread_id": "t1"}}
    app.invoke(
        {
            "members_input": "a b",
            "must_link_groups_input": "",
            "cannot_link_groups_input": "",
        },
        config=config,
    )

    assert len(fake_llm.team_prompts) == 2
    retry_prompt_text = fake_llm.team_prompts[1][-1].content
    assert "must_link 위반: a, b가 다른 팀" in retry_prompt_text


def test_first_ever_generation_has_no_evaluation_reason_section(fake_llm):
    app = builder_mod.graph_builder()
    config = {"configurable": {"thread_id": "t2"}}
    app.invoke(
        {
            "members_input": "a b",
            "must_link_groups_input": "",
            "cannot_link_groups_input": "",
        },
        config=config,
    )

    first_prompt_text = fake_llm.team_prompts[0][-1].content
    assert "이전 시도 검증 실패 사유" not in first_prompt_text
```

- [ ] **Step 2: 테스트 실행 → 첫 번째 테스트 실패 확인**

Run: `PYTHONPATH=. uv run pytest -q tests/test_team_generator_node.py`
Expected: `test_fail_reason_is_fed_back_into_the_retry_prompt` FAIL (재시도 프롬프트에 FAIL 사유 텍스트가 없음). 두 번째 테스트는 이미 PASS.

- [ ] **Step 3: `build_team_generator_prompt`에 evaluation_reason 섹션 추가**

`app/utils/build_team_generator_base_prompt_section.py`의 함수 시그니처와 본문을 수정:

```python
def build_team_generator_prompt(
    score_groups: dict[int, list[str]],
    must_link_groups: list[list[str]],
    cannot_link_groups: list[list[str]],
    feedback: str | None,
    team_a: list[str] | None,
    team_b: list[str] | None,
    evaluation_reason: str | None = None,
):
```

`prompt_sections = [base_prompt_section]` 다음, 기존 `feedback_section = f"""..."""` 블록 **이전**에 아래를 추가:

```python
    evaluation_reason_section = f"""
---

## 이전 시도 검증 실패 사유

아래 사유로 직전 시도가 검증을 통과하지 못했습니다. 이 문제를 해결하도록 다시 생성하세요.

### evaluation_reason
{evaluation_reason}

### previous_team_a
{team_a}

### previous_team_b
{team_b}
"""

    if evaluation_reason:
        prompt_sections.append(evaluation_reason_section)
```

- [ ] **Step 4: team_generator_node가 evaluation_reason을 전달하도록 수정**

`app/graph/nodes/team_generator_node.py`를 수정:

```python
from app.graph.state import TeamState
from app.utils.build_team_generator_base_prompt_section import build_team_generator_prompt
from app.utils.group_members_by_score import group_members_by_score

def team_generator_node(state: TeamState, structured_llm) -> TeamState:
    members = state["members"]
    member_scores = state["member_scores"]
    team_a = state.get("team_a")
    team_b = state.get("team_b")
    must_link_groups = state["must_link_groups"]
    cannot_link_groups = state["cannot_link_groups"]
    feedback = state.get("feedback", "")
    evaluation_reason = (
        state.get("evaluation_reason")
        if state.get("evaluation_status") == "FAIL"
        else None
    )

    score_groups = group_members_by_score(
      members,
      member_scores,
    )

    prompt = build_team_generator_prompt(
        score_groups, 
        must_link_groups, 
        cannot_link_groups,
        feedback,
        team_a,
        team_b,
        evaluation_reason,
    )

    print("팀 생성 중 ..")

    res = structured_llm.invoke(prompt)

    message = f"팀 생성 완료"
    print(message)
    print(f"res========= {res}")

    return {
        "messages": [message],
        "team_a": res.team_a,
        "team_b": res.team_b,
        "score_diff": res.score_diff,
        "output_reason": res.reason,
    }
```

(`evaluation_status == "FAIL"`일 때만 reason을 넘기는 이유: human_approval 이후 사람 피드백으로 재생성할 때, 직전 라운드가 이미 PASS였다면 오래된 PASS 사유가 다시 끼어들지 않게 한다.)

- [ ] **Step 5: 테스트 재실행 → 전체 통과 확인**

Run: `PYTHONPATH=. uv run pytest -q tests/test_team_generator_node.py`
Expected: `2 passed`

- [ ] **Step 6: 회귀 확인 (이전 태스크 테스트도 같이)**

Run: `PYTHONPATH=. uv run pytest -q`
Expected: 지금까지 작성한 모든 테스트 PASS

- [ ] **Step 7: Commit**

```bash
git add app/utils/build_team_generator_base_prompt_section.py app/graph/nodes/team_generator_node.py tests/test_team_generator_node.py
git commit -m "fix: feed evaluator FAIL reason back into the regeneration prompt"
```

---

### Task 4: main.py — 매 생성마다 새 thread_id 발급 + feedback 평문 전달 + EMPTY 필터링 + FAIL 상태 노출

**문제:** [app/main.py](app/main.py)에 네 가지 버그가 몰려 있다.
1. ([app/main.py:26-27](app/main.py#L26-L27)) `thread_id`가 세션 전체에서 한 번만 생성되어, "팀 생성"을 다시 눌러도 LangGraph 체크포인터가 이전 실행의 `feedback`/`team_a`/`team_b`/`evaluation_count`를 그대로 이어받는다. (재현 확인됨: fake LLM으로 두 번 연속 생성 시 `thread_1 == thread_2`.)
2. ([app/main.py:118-123](app/main.py#L118-L123)) `Command(resume={"feedback": feedback_input})`로 dict를 넘겨서, `human_approval_node`의 `interrupt()`가 그 dict를 그대로 받아 `state["feedback"]`이 문자열이 아니라 dict가 된다.
3. ([app/main.py:82, 135](app/main.py#L82)) 홀수 인원일 때 추가된 `'EMPTY'` 더미가 필터링 없이 화면에 그대로 노출된다.
4. evaluator가 FAIL 상태로 human_approval에 도달해도 `evaluation_status`/`evaluation_reason`을 화면에 보여주지 않아 사용자가 제약 위반을 모르고 승인할 수 있다.

네 가지 모두 같은 파일의 좁은 영역을 건드리고 함께 테스트하는 게 자연스러워 한 태스크로 묶는다.

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_main_app.py`

**Interfaces:**
- Produces: `app/main.py`에 `build_team_message(values: dict) -> str` 함수 추가 — `values["team_a"]`/`values["team_b"]`에서 `"EMPTY"`를 제외하고 합치고, `values.get("evaluation_status") == "FAIL"`이면 경고 문구를 덧붙인다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_main_app.py`:

```python
from streamlit.testing.v1 import AppTest

from app.schemas.evaluation_schema import EvaluationSchema
from app.schemas.team_schema import TeamSchema


def _generate(at, members_text):
    at.text_input[0].input(members_text).run()
    at.button[0].click().run()


def test_each_new_generation_gets_a_fresh_thread_id(fake_llm):
    at = AppTest.from_file("app/main.py")
    at.run()

    _generate(at, "a b")
    thread_1 = at.session_state["thread_id"]

    _generate(at, "c d e f")
    thread_2 = at.session_state["thread_id"]

    assert thread_1 != thread_2


def test_empty_placeholder_member_is_not_shown_to_the_user(fake_llm):
    fake_llm.team_responses = [
        TeamSchema(team_a=["a", "EMPTY"], team_b=["b", "c"], score_diff=0, reason="fake")
    ]

    at = AppTest.from_file("app/main.py")
    at.run()
    _generate(at, "a b c")

    rendered = at.chat_message[-1].markdown[0].value
    assert "EMPTY" not in rendered


def test_fail_status_is_surfaced_to_the_user(fake_llm):
    fake_llm.eval_responses = [
        EvaluationSchema(status="FAIL", reason="cannot_link 위반: a, b가 같은 팀")
    ]

    at = AppTest.from_file("app/main.py")
    at.run()
    _generate(at, "a b")

    rendered = at.chat_message[-1].markdown[0].value
    assert "검증 실패" in rendered
    assert "cannot_link 위반: a, b가 같은 팀" in rendered


def test_feedback_reaches_the_prompt_as_plain_text_not_a_dict(fake_llm):
    at = AppTest.from_file("app/main.py")
    at.run()
    _generate(at, "a b")

    at.chat_input[0].set_value("a와 b는 같은 팀으로").run()

    retry_prompt_text = fake_llm.team_prompts[-1][-1].content
    assert "a와 b는 같은 팀으로" in retry_prompt_text
    assert "{'feedback'" not in retry_prompt_text
```

- [ ] **Step 2: 테스트 실행 → 4개 모두(또는 일부) 실패 확인**

Run: `PYTHONPATH=. uv run pytest -q tests/test_main_app.py`
Expected: 4개 중 다음 항목들이 FAIL —
- `test_each_new_generation_gets_a_fresh_thread_id`: `thread_1 == thread_2`라서 실패
- `test_empty_placeholder_member_is_not_shown_to_the_user`: 렌더링된 텍스트에 `"EMPTY"`가 포함되어 실패
- `test_fail_status_is_surfaced_to_the_user`: "검증 실패" 문구가 없어서 실패
- `test_feedback_reaches_the_prompt_as_plain_text_not_a_dict`: 프롬프트에 `"{'feedback'"`가 포함되어 실패

- [ ] **Step 3: app/main.py 수정**

`app/main.py` 전체를 아래 내용으로 교체:

```python
from langgraph.types import Command
import streamlit as st
from dotenv import load_dotenv
from app.exceptions.validation import ValidationError
from app.graph.builder import graph_builder
import uuid

load_dotenv()

@st.cache_resource
def get_app():
    return graph_builder()


def build_team_message(values: dict) -> str:
    team_a = " ".join(m for m in values["team_a"] if m != "EMPTY")
    team_b = " ".join(m for m in values["team_b"] if m != "EMPTY")
    message = f"🔵 블루팀\n\n{team_a}\n\n🟡 골드팀\n\n{team_b}"

    if values.get("evaluation_status") == "FAIL":
        message += f"\n\n⚠️ 검증 실패 (자동 재시도 한도 도달)\n{values.get('evaluation_reason', '')}"

    return message


app = get_app()

st.title("Team Balancer")

input_container = st.container()

with input_container:
    members_input = st.text_input("팀원 이름 (띄어쓰기)")
    cannot_link_groups_input = st.text_input("분리 그룹 (선택) 예: a/b, c/d")
    must_link_groups_input = st.text_input("묶음 그룹 (선택) 예: a-b, c-d-e")
    team_create_button_clicked = st.button("팀 생성")

if "awaiting_approval" not in st.session_state:
    st.session_state.awaiting_approval = False

if "config" not in st.session_state:
    st.session_state.config = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if team_create_button_clicked:
    st.session_state.awaiting_approval = False
    st.session_state.config = None

    if not members_input: 
        st.warning("팀원을 입력해주세요.")
    else:
        st.session_state.thread_id = str(uuid.uuid4())

        st.session_state.messages.append({
            "role": "user",
            "content": f"""
            팀원: {members_input}

            분리 그룹: {cannot_link_groups_input}

            묶음 그룹: {must_link_groups_input}
        """})

        msg = st.info("팀 생성 중 ..")

        try:
            config = {
                "configurable": {
                    "thread_id": st.session_state.thread_id
                }
            }

            app.invoke(
                {
                    "members_input": members_input,
                    "must_link_groups_input": must_link_groups_input,
                    "cannot_link_groups_input": cannot_link_groups_input,
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
            msg.empty()
            st.error(str(e) + ". 입력을 수정한 후 다시 팀 생성 버튼을 눌러주세요.")
        except Exception as e:
            msg.empty()
            st.error("알 수 없는 오류가 발생했습니다. 입력을 수정한 후 다시 팀 생성 버튼을 눌러주세요.")
            st.exception(e)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if st.session_state.awaiting_approval:
    snapshot = app.get_state(st.session_state.config)

    values = snapshot.values

    msg = st.info("팀 생성 완료. 수정 사항이 있으면 입력해주세요.")

    feedback_input = st.chat_input(
        "예: 김철수와 박영희는 같은 팀으로",
    )

    if feedback_input:
        st.session_state.messages.append({
            "role": "user",
            "content": feedback_input,
        })

        msg.empty()
        msg = st.info("수정 반영 중 ..")

        app.invoke(
            Command(resume=feedback_input),
            config=st.session_state.config,
        )

        msg.empty()

        snapshot = app.get_state(st.session_state.config)

        values = snapshot.values

        st.session_state.messages.append({
            "role": "assistant",
            "content": build_team_message(values),
        })
        st.rerun()
```

주요 변경점:
- `if "thread_id" not in st.session_state: ...` 초기화 블록 제거 → 버튼 클릭 시(`else` 분기) 매번 `st.session_state.thread_id = str(uuid.uuid4())`로 새 thread 발급.
- `build_team_message()` 헬퍼 추가, 두 곳의 assistant 메시지 작성에 사용.
- `Command(resume={"feedback": feedback_input})` → `Command(resume=feedback_input)`.
- 사용하지 않던 `res = app.invoke(...)` 대입 제거(반환값 미사용이었음).

- [ ] **Step 4: 테스트 재실행 → 전체 통과 확인**

Run: `PYTHONPATH=. uv run pytest -q tests/test_main_app.py`
Expected: `4 passed`

- [ ] **Step 5: 회귀 확인 (전체 스위트)**

Run: `PYTHONPATH=. uv run pytest -q`
Expected: 지금까지의 모든 테스트 PASS

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_main_app.py
git commit -m "fix: issue a fresh thread per generation, send feedback as plain text, hide EMPTY placeholder, surface FAIL status"
```

---

### Task 5: 죽은 코드 및 저장소 잔재 정리

**문제:**
- [app/graph/state.py:30-32](app/graph/state.py#L30-L32)의 `retry_count`, `max_retries`, [state.py:38](app/graph/state.py#L38)의 `history` 필드가 선언만 되어 있고 코드 어디서도 읽거나 쓰지 않는다.
- [app/graph/edges.py](app/graph/edges.py)는 빈 파일이며 어디서도 import되지 않는다(엣지 로직은 전부 `builder.py`에 인라인으로 있음).
- `__pycache__/*.pyc` 파일들이 `.gitignore`에 없어 git에 커밋되어 있다. 그중 `build_team_generator_feedback_section.cpython-314.pyc`, `formatter_node.cpython-314.pyc`는 대응하는 소스 파일이 이미 삭제된 잔재다.

이 태스크는 동작을 바꾸지 않는 순수 정리이므로, "실패하는 테스트"를 새로 작성하는 대신 기존 테스트 스위트가 정리 전후로 계속 통과하는 것으로 안전성을 확인한다.

**Files:**
- Modify: `app/graph/state.py`
- Delete: `app/graph/edges.py`
- Modify: `.gitignore`
- Delete (git에서 추적 해제): 커밋되어 있는 `__pycache__` 디렉터리들

- [ ] **Step 1: 정리 전 테스트 스위트가 전부 통과하는지 확인 (베이스라인)**

Run: `PYTHONPATH=. uv run pytest -q`
Expected: 모든 테스트 PASS

- [ ] **Step 2: state.py에서 미사용 필드 제거**

`app/graph/state.py`를 아래로 교체:

```python
from typing import Annotated, Literal, TypedDict, Optional
from langgraph.graph import add_messages

class TeamState(TypedDict):
    messages: Annotated[list[dict], add_messages]

    # Input
    members_input: str
    members: list[str]
    must_link_groups_input: str
    must_link_groups: list[list[str]]
    cannot_link_groups_input: str
    cannot_link_groups: list[list[str]]

    # Data
    member_scores: dict[str, int]
    score_source: str  # (확장: DB / API 구분)

    # Output
    team_a: list[str]
    team_b: list[str]
    score_diff: int
    output_reason: str

    # Eval
    evaluation_status: Literal["PASS", "FAIL"]
    evaluation_reason: str
    evaluation_count: int

    # Feedback
    feedback: Optional[str]
```

(`retry_count`, `max_retries`, `history` 필드와 `# Control`/`# Debug / Trace` 주석 제거)

- [ ] **Step 3: 사용하지 않는 edges.py 삭제**

```bash
rm app/graph/edges.py
```

- [ ] **Step 4: .gitignore에 __pycache__ 추가**

`.gitignore`를 아래로 교체:

```
.env

.venv/
__pycache__/
*.pyc
```

- [ ] **Step 5: 이미 커밋된 __pycache__ 파일들을 git 추적에서 제거**

```bash
git rm -r --cached app/__pycache__ app/exceptions/__pycache__ app/graph/__pycache__ app/graph/nodes/__pycache__ app/llm/__pycache__ app/schemas/__pycache__ app/utils/__pycache__
```

- [ ] **Step 6: 정리 후 테스트 스위트가 여전히 통과하는지 확인**

Run: `PYTHONPATH=. uv run pytest -q`
Expected: 모든 테스트 PASS (Step 1과 동일한 개수)

- [ ] **Step 7: edges.py가 정말 어디서도 참조되지 않았는지 최종 확인**

Run: `grep -rn "graph.edges\|graph import edges" app/ tests/`
Expected: 출력 없음 (참조 없음)

- [ ] **Step 8: Commit**

```bash
git add app/graph/state.py .gitignore
git commit -m "chore: remove dead state fields, unused edges.py, and stop tracking __pycache__"
```

---

## Self-Review

- **Spec coverage:** 점검 결과 8개 항목 모두 태스크에 매핑됨 — #1(의존성)→Task1, #2(thread_id)→Task4, #3(feedback dict)→Task4, #4(EMPTY 노출)→Task4, #5(FAIL 사유 미반영)→Task3, #6(FAIL 미노출)→Task4, #7(split 파싱)→Task2, #8(죽은 코드)→Task5.
- **Placeholder scan:** 모든 스텝에 실행 가능한 전체 코드/명령/예상 출력 포함. "TODO"/"적절히 처리" 류 표현 없음.
- **Type consistency:** `build_team_generator_prompt`의 새 인자 `evaluation_reason`은 Task3에서 정의되고 Task3의 `team_generator_node.py`에서 동일한 이름으로 전달됨. `build_team_message`는 Task4에서 정의·사용이 같은 태스크 내에서 일치함. `fake_llm` fixture는 Task1에서 정의되고 Task2~4에서 동일한 인터페이스(`team_responses`, `eval_responses`, `team_prompts`, `eval_prompts`)로 사용됨.
