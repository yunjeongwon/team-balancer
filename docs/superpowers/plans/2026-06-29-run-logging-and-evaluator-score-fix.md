# Run Logging + Evaluator Score-Sum Fix + Placeholder Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist each team-generation run's progress to a per-thread log file, ground the evaluator's score-balance judgment in code-computed numbers instead of LLM arithmetic, and rename the headcount-padding placeholder member from the misleading `"EMPTY"` to `"(공석)"`.

**Architecture:** Three independent slices applied to the existing LangGraph node pipeline (`input → score_fetch → team_generator → evaluator → human_approval`): (1) a new `app.logging_config` module wires a per-thread-id `FileHandler` + console `StreamHandler` onto a `"team_balancer"` logger that all four nodes write to instead of `print()`; (2) a new pure function `compute_team_score_sum` is used by `evaluator_node` to inject real team score totals into the evaluator's prompt; (3) a new `app.constants.PLACEHOLDER_MEMBER` constant replaces the `"EMPTY"` string literal everywhere it appears.

**Tech Stack:** Python 3.14, stdlib `logging` (no new dependency), pytest, LangGraph, the existing `RecordingFakeLLM` / `fake_llm` fixture in `tests/conftest.py`.

## Global Constraints

- Placeholder member constant: `PLACEHOLDER_MEMBER = "(공석)"`, defined once in `app/constants.py`.
- Logger name used by every node and by `app/logging_config.py`: `"team_balancer"` (exact string, used with `logging.getLogger("team_balancer")`).
- Log directory default: `app.logging_config.LOG_DIR = Path("logs")`, must be a module-level variable (not a function-local constant) so tests can `monkeypatch.setattr` it.
- No new dependencies — only `import logging` / `import pathlib` from the standard library.
- Run tests with `uv run python -m pytest ...`, **not** bare `uv run pytest`. This repo has no `[tool.pytest.ini_options] pythonpath` entry, so a bare `pytest` invocation fails to import the `app` package (`ModuleNotFoundError: No module named 'app'`) — `python -m pytest` puts the current directory on `sys.path` and works correctly.

**Known pre-existing condition (not in scope for this plan):** `tests/test_team_generator_node.py::test_fail_reason_is_fed_back_into_the_retry_prompt` and `::test_first_ever_generation_has_no_evaluation_reason_section` already fail on a clean checkout with `KeyError: 'default_score'`, because they invoke the graph without a `"default_score"` key. This plan does not fix them — every "expected" test count below already accounts for these 2 failures. Any new test added by this plan that invokes the graph directly via `graph_builder()` (bypassing `app/main.py`) must include `"default_score": 4` in its initial state dict to avoid tripping the same pre-existing bug.

---

### Task 1: Rename the placeholder member (`EMPTY` → `PLACEHOLDER_MEMBER = "(공석)"`)

**Files:**
- Create: `app/constants.py`
- Modify: `app/graph/nodes/input_node.py:19`
- Modify: `app/main.py:16-17`
- Modify: `tests/test_input_node.py`
- Modify: `tests/test_main_app.py`

**Interfaces:**
- Produces: `PLACEHOLDER_MEMBER: str` in `app.constants`, value `"(공석)"`.

- [ ] **Step 1: Update the failing test in `tests/test_input_node.py`**

Replace the full file content with:

```python
import pytest

from app.constants import PLACEHOLDER_MEMBER
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
    assert result["members"] == ["a", "b", "c", PLACEHOLDER_MEMBER]


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

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run python -m pytest tests/test_input_node.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'app.constants'`. The new top-level import makes the whole file fail to collect, so all 4 tests in it report as errored, not just the one touching the placeholder. This is expected until Step 3 creates the module.

- [ ] **Step 3: Create `app/constants.py`**

```python
PLACEHOLDER_MEMBER = "(공석)"
```

- [ ] **Step 4: Run the test again to verify it still fails, now on the assertion**

Run: `uv run python -m pytest tests/test_input_node.py -v`
Expected: `test_collapses_repeated_spaces_instead_of_creating_blank_member` FAILS with `AssertionError` (`input_node` still appends the literal `'EMPTY'`, not `"(공석)"`).

- [ ] **Step 5: Update `app/graph/nodes/input_node.py`**

Replace the full file content with:

```python
from app.constants import PLACEHOLDER_MEMBER
from app.exceptions.validation import ValidationError
from app.graph.state import TeamState
from app.utils.parse_pairs_input import parse_group_input

def input_node(state: TeamState) -> TeamState:
    members_input = state["members_input"]
    must_link_groups_input = state["must_link_groups_input"]
    cannot_link_groups_input = state["cannot_link_groups_input"]

    # members_input => members
    members = members_input.split()

    member_set = set(members)
    if len(member_set) != len(members):
        raise ValidationError("중복된 팀원이 존재합니다.")

    # 짝수 맞추기
    if len(members) % 2 == 1:
        members.append(PLACEHOLDER_MEMBER)

    # groups_input => groups
    must_link_groups = parse_group_input(must_link_groups_input, "-")
    cannot_link_groups = parse_group_input(cannot_link_groups_input, "/")
    
    # validation
    for group in must_link_groups + cannot_link_groups:
        for member in group:
            if member not in member_set:
                raise ValidationError(
                f"존재하지 않는 팀원이 포함되어 있습니다: {member}"
            )

    message = f"입력 파싱 완료"
    print(message)

    return {
        "messages": [message],
        "members": members,
        "must_link_groups": must_link_groups,
        "cannot_link_groups": cannot_link_groups,
    }
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run python -m pytest tests/test_input_node.py -v`
Expected: `4 passed`

- [ ] **Step 7: Update the failing test in `tests/test_main_app.py`**

Replace the full file content with:

```python
from streamlit.testing.v1 import AppTest

from app.constants import PLACEHOLDER_MEMBER
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
        TeamSchema(team_a=["a", PLACEHOLDER_MEMBER], team_b=["b", "c"], score_diff=0, reason="fake")
    ]

    at = AppTest.from_file("app/main.py")
    at.run()
    _generate(at, "a b c")

    rendered = at.chat_message[-1].markdown[0].value
    assert PLACEHOLDER_MEMBER not in rendered


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

- [ ] **Step 8: Run the test to verify it fails**

Run: `uv run python -m pytest tests/test_main_app.py -v`
Expected: `test_empty_placeholder_member_is_not_shown_to_the_user` FAILS with `AssertionError` (`app/main.py` still filters on the literal `"EMPTY"`, so `"(공석)"` is not removed and shows up in `rendered`).

- [ ] **Step 9: Update `app/main.py`**

Change the imports at the top of the file from:

```python
from langgraph.types import Command
import streamlit as st
from dotenv import load_dotenv
from app.exceptions.validation import ValidationError
from app.graph.builder import graph_builder
import uuid
```

to:

```python
from langgraph.types import Command
import streamlit as st
from dotenv import load_dotenv
from app.constants import PLACEHOLDER_MEMBER
from app.exceptions.validation import ValidationError
from app.graph.builder import graph_builder
import uuid
```

Change `build_team_message` from:

```python
def build_team_message(values: dict) -> str:
    team_a = " ".join(m for m in values["team_a"] if m != "EMPTY")
    team_b = " ".join(m for m in values["team_b"] if m != "EMPTY")
    message = f"🔵 블루팀\n\n{team_a}\n\n🟡 골드팀\n\n{team_b}"
```

to:

```python
def build_team_message(values: dict) -> str:
    team_a = " ".join(m for m in values["team_a"] if m != PLACEHOLDER_MEMBER)
    team_b = " ".join(m for m in values["team_b"] if m != PLACEHOLDER_MEMBER)
    message = f"🔵 블루팀\n\n{team_a}\n\n🟡 골드팀\n\n{team_b}"
```

- [ ] **Step 10: Run the test to verify it passes**

Run: `uv run python -m pytest tests/test_main_app.py -v`
Expected: `4 passed`

- [ ] **Step 11: Run the full suite to confirm no regressions**

Run: `uv run python -m pytest -q`
Expected: `9 passed, 2 failed` (the 2 failures are the pre-existing `default_score` ones called out in Global Constraints — unchanged from baseline)

- [ ] **Step 12: Commit**

```bash
git add app/constants.py app/graph/nodes/input_node.py app/main.py tests/test_input_node.py tests/test_main_app.py
git commit -m "refactor: rename EMPTY placeholder member to PLACEHOLDER_MEMBER (공석)"
```

---

### Task 2: Per-run file logging infrastructure

**Files:**
- Create: `app/logging_config.py`
- Create: `tests/test_logging_config.py`
- Modify: `tests/conftest.py`
- Modify: `app/main.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `configure_run_logging(thread_id: str) -> None` and module variable `LOG_DIR: pathlib.Path` in `app.logging_config`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_logging_config.py`:

```python
import logging

import app.logging_config as logging_config


def test_configure_run_logging_creates_a_file_named_after_the_thread_id(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)

    logging_config.configure_run_logging("thread-abc")
    logging.getLogger("team_balancer").info("hello")

    log_file = tmp_path / "thread-abc.log"
    assert log_file.exists()
    assert "hello" in log_file.read_text(encoding="utf-8")


def test_configure_run_logging_appends_when_called_again_for_the_same_thread_id(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)
    logger = logging.getLogger("team_balancer")

    logging_config.configure_run_logging("thread-abc")
    logger.info("first")
    logging_config.configure_run_logging("thread-abc")
    logger.info("second")

    log_file = tmp_path / "thread-abc.log"
    content = log_file.read_text(encoding="utf-8")
    assert "first" in content
    assert "second" in content
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run python -m pytest tests/test_logging_config.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'app.logging_config'` (both tests in this brand-new file are affected, since the import happens before either test runs)

- [ ] **Step 3: Create `app/logging_config.py`**

```python
import logging
from pathlib import Path

LOG_DIR = Path("logs")


def configure_run_logging(thread_id: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("team_balancer")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(LOG_DIR / f"{thread_id}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run python -m pytest tests/test_logging_config.py -v`
Expected: `2 passed`

- [ ] **Step 5: Add an autouse fixture to `tests/conftest.py` so other tests never touch the real `logs/` directory**

The current `tests/conftest.py` is:

```python
import pytest
import streamlit as st

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

    # app/main.py's get_app()는 @st.cache_resource로 감싸여 있는데, Streamlit이
    # 함수 소스 기준으로 캐시 키를 정하기 때문에, 비워주지 않으면
    # AppTest 기반 테스트가 다른 테스트의 (다른 fake_llm으로 만들어진) 캐시된
    # 그래프를 재사용해버린다.
    st.cache_resource.clear()

    llm = RecordingFakeLLM()
    monkeypatch.setattr(builder_mod, "get_model", lambda: llm)
    return llm
```

Add a new autouse fixture at the end of the file:

```python
@pytest.fixture(autouse=True)
def isolate_run_logs(tmp_path, monkeypatch):
    import app.logging_config as logging_config

    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path / "logs")
```

- [ ] **Step 6: Add `logs/` to `.gitignore`**

The current `.gitignore` is:

```
.env

.venv/
__pycache__/
*.pyc
```

Append a line so it reads:

```
.env

.venv/
__pycache__/
*.pyc
logs/
```

- [ ] **Step 7: Wire `configure_run_logging` into `app/main.py`**

Change the imports from (current state, after Task 1):

```python
from langgraph.types import Command
import streamlit as st
from dotenv import load_dotenv
from app.constants import PLACEHOLDER_MEMBER
from app.exceptions.validation import ValidationError
from app.graph.builder import graph_builder
import uuid
```

to:

```python
from langgraph.types import Command
import streamlit as st
from dotenv import load_dotenv
from app.constants import PLACEHOLDER_MEMBER
from app.exceptions.validation import ValidationError
from app.graph.builder import graph_builder
from app.logging_config import configure_run_logging
import uuid
```

Change:

```python
        st.session_state.thread_id = str(uuid.uuid4())

        st.session_state.messages.append({
```

to:

```python
        st.session_state.thread_id = str(uuid.uuid4())
        configure_run_logging(st.session_state.thread_id)

        st.session_state.messages.append({
```

Change:

```python
        msg.empty()
        msg = st.info("수정 반영 중 ..")

        app.invoke(
            Command(resume=feedback_input),
            config=st.session_state.config,
        )
```

to:

```python
        msg.empty()
        msg = st.info("수정 반영 중 ..")

        configure_run_logging(st.session_state.thread_id)
        app.invoke(
            Command(resume=feedback_input),
            config=st.session_state.config,
        )
```

- [ ] **Step 8: Run the full suite to confirm no regressions and no real `logs/` pollution**

Run: `uv run python -m pytest -q`
Expected: `11 passed, 2 failed` (2 pre-existing, see Global Constraints)

Run: `git status --short logs/ 2>/dev/null; ls logs/ 2>/dev/null`
Expected: no output (the real `logs/` directory was never created — the autouse fixture redirected every test run to `tmp_path`)

- [ ] **Step 9: Commit**

```bash
git add app/logging_config.py tests/test_logging_config.py tests/conftest.py app/main.py .gitignore
git commit -m "feat: add per-run file logging via app.logging_config"
```

---

### Task 3: Replace `print()` with `logger.info()` in the four pipeline nodes

**Files:**
- Modify: `app/graph/nodes/input_node.py`
- Modify: `app/graph/nodes/score_fetch_node.py`
- Modify: `app/graph/nodes/team_generator_node.py`
- Modify: `app/graph/nodes/evaluator_node.py`
- Create: `tests/test_node_logging.py`

**Interfaces:**
- Consumes: logger name `"team_balancer"` from `app.logging_config` (Task 2).
- Produces: each node module now exposes a module-level `logger = logging.getLogger("team_balancer")` that Task 5 will reuse in `evaluator_node.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_node_logging.py`:

```python
import logging

import app.graph.builder as builder_mod


def test_each_node_logs_its_progress_message(fake_llm, caplog):
    app = builder_mod.graph_builder()
    config = {"configurable": {"thread_id": "t-log"}}

    with caplog.at_level(logging.INFO, logger="team_balancer"):
        app.invoke(
            {
                "members_input": "a b",
                "must_link_groups_input": "",
                "cannot_link_groups_input": "",
                "default_score": 4,
            },
            config=config,
        )

    messages = [record.message for record in caplog.records]
    assert "입력 파싱 완료" in messages
    assert "가중치 적용 완료" in messages
    assert "팀 생성 중 .." in messages
    assert "팀 생성 완료" in messages
    assert "'1번째' 검증 중 .." in messages
    assert "'1번째' 검증 완료" in messages
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run python -m pytest tests/test_node_logging.py -v`
Expected: FAILS with `AssertionError` (`caplog.records` is empty — the nodes still use `print`, nothing reaches the `"team_balancer"` logger)

- [ ] **Step 3: Update `app/graph/nodes/input_node.py`**

Add `import logging` as the first line and a module-level logger, and swap the `print`:

```python
import logging

from app.constants import PLACEHOLDER_MEMBER
from app.exceptions.validation import ValidationError
from app.graph.state import TeamState
from app.utils.parse_pairs_input import parse_group_input

logger = logging.getLogger("team_balancer")

def input_node(state: TeamState) -> TeamState:
    members_input = state["members_input"]
    must_link_groups_input = state["must_link_groups_input"]
    cannot_link_groups_input = state["cannot_link_groups_input"]

    # members_input => members
    members = members_input.split()

    member_set = set(members)
    if len(member_set) != len(members):
        raise ValidationError("중복된 팀원이 존재합니다.")

    # 짝수 맞추기
    if len(members) % 2 == 1:
        members.append(PLACEHOLDER_MEMBER)

    # groups_input => groups
    must_link_groups = parse_group_input(must_link_groups_input, "-")
    cannot_link_groups = parse_group_input(cannot_link_groups_input, "/")
    
    # validation
    for group in must_link_groups + cannot_link_groups:
        for member in group:
            if member not in member_set:
                raise ValidationError(
                f"존재하지 않는 팀원이 포함되어 있습니다: {member}"
            )

    message = f"입력 파싱 완료"
    logger.info(message)

    return {
        "messages": [message],
        "members": members,
        "must_link_groups": must_link_groups,
        "cannot_link_groups": cannot_link_groups,
    }
```

- [ ] **Step 4: Update `app/graph/nodes/score_fetch_node.py`**

Replace the full file content with:

```python
import logging

from app.graph.state import TeamState
from app.utils.load_scores import load_scores

logger = logging.getLogger("team_balancer")

def score_fetch_node(state: TeamState) -> TeamState:
    members = state["members"]
    default_score = state["default_score"]
    scores = load_scores()

    member_scores = {}
    for member in members:
        member_scores[member] = scores.get(member, default_score)

    message = f"가중치 적용 완료"
    logger.info(message)

    return {
        "messages": [message],
        "member_scores": member_scores,
        "score_source": "data/scores.json",
    }
```

- [ ] **Step 5: Update `app/graph/nodes/team_generator_node.py`**

Replace the full file content with:

```python
import logging

from app.graph.state import TeamState
from app.utils.build_team_generator_base_prompt_section import build_team_generator_prompt
from app.utils.group_members_by_score import group_members_by_score

logger = logging.getLogger("team_balancer")

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

    logger.info("팀 생성 중 ..")

    res = structured_llm.invoke(prompt)

    message = f"팀 생성 완료"
    logger.info(message)
    logger.info(f"res========= {res}")

    return {
        "messages": [message],
        "team_a": res.team_a,
        "team_b": res.team_b,
        "score_diff": res.score_diff,
        "output_reason": res.reason,
    }
```

- [ ] **Step 6: Update `app/graph/nodes/evaluator_node.py`**

Replace the full file content with:

```python
import logging

from app.graph.state import TeamState
from app.utils.format_groups import format_groups
from app.utils.build_evaluator_prompt import build_evaluator_prompt
from app.utils.format_score_groups import format_score_groups
from app.utils.format_team import format_team
from app.utils.group_members_by_score import group_members_by_score

logger = logging.getLogger("team_balancer")

def evaluator_node(state: TeamState, structured_llm) -> TeamState:
    members = state["members"]
    member_scores = state["member_scores"]
    team_a = state["team_a"]
    team_b = state["team_b"]
    must_link_groups = state["must_link_groups"]
    cannot_link_groups = state["cannot_link_groups"]
    feedback = state.get("feedback", "")
    evaluation_count = state.get("evaluation_count", 0)

    score_groups = group_members_by_score(
      members,
      member_scores,
    )

    prompt = build_evaluator_prompt(
            members,
            score_groups,
            must_link_groups,
            cannot_link_groups,
            feedback,
            team_a,
            team_b,
    )

    logger.info(f"'{evaluation_count + 1}번째' 검증 중 ..")
    
    res = structured_llm.invoke(prompt)

    message = f"'{evaluation_count + 1}번째' 검증 완료"
    logger.info(message)
    logger.info(res)

    return {
        "messages": [message],
        "evaluation_status": res.status,
        "evaluation_reason": res.reason,
        "evaluation_count": evaluation_count + 1
    }
```

(Task 5 will modify this file again to add the score-sum computation — this step only swaps `print` for `logger.info`.)

- [ ] **Step 7: Run the test to verify it passes**

Run: `uv run python -m pytest tests/test_node_logging.py -v`
Expected: `1 passed`

- [ ] **Step 8: Run the full suite to confirm no regressions**

Run: `uv run python -m pytest -q`
Expected: `12 passed, 2 failed` (2 pre-existing, see Global Constraints)

- [ ] **Step 9: Commit**

```bash
git add app/graph/nodes/input_node.py app/graph/nodes/score_fetch_node.py app/graph/nodes/team_generator_node.py app/graph/nodes/evaluator_node.py tests/test_node_logging.py
git commit -m "refactor: replace print() with logger.info() in pipeline nodes"
```

---

### Task 4: `compute_team_score_sum` utility

**Files:**
- Create: `app/utils/compute_team_score_sum.py`
- Create: `tests/test_compute_team_score_sum.py`

**Interfaces:**
- Produces: `compute_team_score_sum(team: list[str], member_scores: dict[str, int]) -> int` in `app.utils.compute_team_score_sum`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_compute_team_score_sum.py`:

```python
from app.utils.compute_team_score_sum import compute_team_score_sum


def test_sums_each_members_score():
    member_scores = {"a": 5, "b": 3, "c": 4}

    assert compute_team_score_sum(["a", "b"], member_scores) == 8
    assert compute_team_score_sum(["c"], member_scores) == 4


def test_placeholder_member_is_counted_like_any_other_member():
    member_scores = {"a": 5, "(공석)": 4}

    assert compute_team_score_sum(["a", "(공석)"], member_scores) == 9
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run python -m pytest tests/test_compute_team_score_sum.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'app.utils.compute_team_score_sum'` (both tests in this brand-new file are affected, since the import happens before either test runs)

- [ ] **Step 3: Create `app/utils/compute_team_score_sum.py`**

```python
def compute_team_score_sum(team: list[str], member_scores: dict[str, int]) -> int:
    return sum(member_scores[member] for member in team)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run python -m pytest tests/test_compute_team_score_sum.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add app/utils/compute_team_score_sum.py tests/test_compute_team_score_sum.py
git commit -m "feat: add compute_team_score_sum utility"
```

---

### Task 5: Ground the evaluator prompt in computed team score sums

**Files:**
- Modify: `app/utils/build_evaluator_prompt.py`
- Modify: `app/graph/nodes/evaluator_node.py`
- Modify: `tests/test_team_generator_node.py`

**Interfaces:**
- Consumes: `compute_team_score_sum(team: list[str], member_scores: dict[str, int]) -> int` (Task 4); `logger` module variable already defined in `evaluator_node.py` (Task 3).
- Produces: `build_evaluator_prompt(members, score_groups, must_link_groups, cannot_link_groups, feedback, team_a, team_b, team_a_score_sum, team_b_score_sum)` (two new trailing parameters).

- [ ] **Step 1: Write the failing test**

Add this test function to the end of `tests/test_team_generator_node.py`:

```python
def test_evaluator_prompt_includes_computed_team_score_sums(fake_llm):
    fake_llm.team_responses = [
        TeamSchema(team_a=["a"], team_b=["b"], score_diff=0, reason="try-1"),
    ]

    app = builder_mod.graph_builder()
    config = {"configurable": {"thread_id": "t3"}}
    app.invoke(
        {
            "members_input": "a b",
            "must_link_groups_input": "",
            "cannot_link_groups_input": "",
            "default_score": 4,
        },
        config=config,
    )

    eval_prompt_text = fake_llm.eval_prompts[0][-1].content
    assert "team_a_score_sum:\n4" in eval_prompt_text
    assert "team_b_score_sum:\n4" in eval_prompt_text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run python -m pytest tests/test_team_generator_node.py -v`
Expected: `3 failed`. This file already has the 2 pre-existing `default_score` failures from Global Constraints — those still fail for their own unrelated reason. The new `test_evaluator_prompt_includes_computed_team_score_sums` fails too, but with `AssertionError` (the prompt has no `team_a_score_sum` section yet) — that's the one this step is about.

- [ ] **Step 3: Update `app/utils/build_evaluator_prompt.py`**

Replace the full file content with:

```python
from langchain_core.messages import HumanMessage, SystemMessage


def build_evaluator_prompt(
    members: list[str],
    score_groups: dict[int, list[str]],
    must_link_groups: list[list[str]],
    cannot_link_groups: list[list[str]],
    feedback: str | None,
    team_a: list[str],
    team_b: list[str],
    team_a_score_sum: int,
    team_b_score_sum: int,
):
    human_message_content = f"""
# 입력 데이터

members:
{members}

score_groups:
{score_groups}

must_link_groups:
{must_link_groups}

cannot_link_groups:
{cannot_link_groups}

feedback:
{feedback}

result_team_a:
{team_a}

result_team_b:
{team_b}

team_a_score_sum:
{team_a_score_sum}

team_b_score_sum:
{team_b_score_sum}

---

# 역할

당신은 팀 분배 결과를 검증하는 Evaluator 입니다.

당신은 오직 검증만 수행해야 합니다.

금지:
- 새로운 팀 생성
- 더 나은 조합 탐색
- 팀 재배치 제안
- 최적화 수행

---

# Hard Constraints

아래 조건은 반드시 만족해야 합니다.

1. 두 팀 인원 수는 동일해야 함
2. must_link_groups 멤버는 반드시 같은 팀이어야 함
3. cannot_link_groups 멤버는 반드시 서로 다른 팀이어야 함
4. 모든 members 는 정확히 하나의 팀에만 존재해야 함
5. 멤버 누락 금지
6. 멤버 중복 금지
7. 존재하지 않는 멤버 포함 금지

중요:
- 그룹을 하나의 인원으로 계산하지 말고
  그룹 내부 모든 멤버를 개별적으로 검증할 것

판정 규칙:
- Hard Constraints 위반이 하나라도 있으면 즉시 FAIL

---

# Soft Evaluation

Hard Constraints 를 모두 통과한 경우에만 아래를 평가하세요.

평가 항목:
- 팀 총 점수 균형
- 점수 분포 균형
- 특정 점수대 쏠림 여부
- feedback 반영 여부

중요:
- 총점만 비슷하다고 균형이라고 판단하지 말 것
- 특정 강한 멤버 쏠림이 있으면 reason 에 명시할 것
- Soft Evaluation 만으로 FAIL 처리하지 말 것
- team_a_score_sum, team_b_score_sum 값을 그대로 사용할 것. score_groups 에서 직접 재계산하지 말 것

---

# 검증 순서

아래 순서대로 검증하세요.

1. 팀 인원 수 검증
2. 멤버 커버리지 검증
3. must_link_groups 검증
4. cannot_link_groups 검증
5. 점수 균형 및 분포 평가
6. feedback 반영 여부 평가

---

# 출력 규칙

반드시 JSON 만 출력하세요.

추가 설명 금지.
마크다운 금지.
코드블록 금지.

형식:

{{
  "status": "PASS" | "FAIL",
  "reason": "구체적인 판단 근거"
}}
"""

    prompt = [
        SystemMessage(
            content="""
당신은 제약 조건 기반 팀 분배 결과를 검증하는 Evaluator 입니다.

당신의 역할은:
- Hard Constraints 검증
- 점수 균형 평가
- 점수 분포 평가
- feedback 반영 여부 평가

당신은 검증만 수행해야 합니다.
"""
        ),
        HumanMessage(content=human_message_content),
    ]

    return prompt
```

- [ ] **Step 4: Update `app/graph/nodes/evaluator_node.py`**

Replace the full file content with:

```python
import logging

from app.graph.state import TeamState
from app.utils.compute_team_score_sum import compute_team_score_sum
from app.utils.format_groups import format_groups
from app.utils.build_evaluator_prompt import build_evaluator_prompt
from app.utils.format_score_groups import format_score_groups
from app.utils.format_team import format_team
from app.utils.group_members_by_score import group_members_by_score

logger = logging.getLogger("team_balancer")

def evaluator_node(state: TeamState, structured_llm) -> TeamState:
    members = state["members"]
    member_scores = state["member_scores"]
    team_a = state["team_a"]
    team_b = state["team_b"]
    must_link_groups = state["must_link_groups"]
    cannot_link_groups = state["cannot_link_groups"]
    feedback = state.get("feedback", "")
    evaluation_count = state.get("evaluation_count", 0)

    score_groups = group_members_by_score(
      members,
      member_scores,
    )

    team_a_score_sum = compute_team_score_sum(team_a, member_scores)
    team_b_score_sum = compute_team_score_sum(team_b, member_scores)
    logger.info(f"team_a_score_sum={team_a_score_sum} team_b_score_sum={team_b_score_sum}")

    prompt = build_evaluator_prompt(
            members,
            score_groups,
            must_link_groups,
            cannot_link_groups,
            feedback,
            team_a,
            team_b,
            team_a_score_sum,
            team_b_score_sum,
    )

    logger.info(f"'{evaluation_count + 1}번째' 검증 중 ..")
    
    res = structured_llm.invoke(prompt)

    message = f"'{evaluation_count + 1}번째' 검증 완료"
    logger.info(message)
    logger.info(res)

    return {
        "messages": [message],
        "evaluation_status": res.status,
        "evaluation_reason": res.reason,
        "evaluation_count": evaluation_count + 1
    }
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run python -m pytest tests/test_team_generator_node.py -v`
Expected: `1 passed, 2 failed` — `test_evaluator_prompt_includes_computed_team_score_sums` now PASSES; the same 2 pre-existing `default_score` failures remain (unrelated to this task, see Global Constraints).

- [ ] **Step 6: Run the full suite to confirm no regressions**

Run: `uv run python -m pytest -q`
Expected: `15 passed, 2 failed` (2 pre-existing, see Global Constraints)

- [ ] **Step 7: Commit**

```bash
git add app/utils/build_evaluator_prompt.py app/graph/nodes/evaluator_node.py tests/test_team_generator_node.py
git commit -m "feat: ground evaluator soft-eval in code-computed team score sums"
```
