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

    # app/main.py's get_app() is wrapped in @st.cache_resource, which
    # Streamlit keys by the function's source rather than object identity.
    # Without clearing it, AppTest-based tests would reuse another test's
    # cached graph (built against a different fake_llm instance).
    st.cache_resource.clear()

    llm = RecordingFakeLLM()
    monkeypatch.setattr(builder_mod, "get_model", lambda use_gpt: llm)
    return llm


@pytest.fixture(autouse=True)
def isolate_run_logs(tmp_path, monkeypatch):
    import app.logging_config as logging_config

    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path / "logs")


@pytest.fixture(autouse=True)
def isolate_github_token(monkeypatch):
    """점수 영속성 테스트가 .env 의 GITHUB_TOKEN 에 영향받지 않도록 env 에서 제거.
    load_scores.load_dotenv() 가 import 시 .env 를 env 로 로드하므로, 이를 가리지 않으면
    로컬 분기 테스트(test_save_scores)가 github 분기로 빠져 requests 호출을 시도한다.
    github 분기를 테스트하려면 각 테스트가 monkeypatch.setenv 로 명시적으로 설정."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
