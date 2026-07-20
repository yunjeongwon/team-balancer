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
    """점수 영속성 테스트가 .env 의 GITHUB_TOKEN 에 영향받지 않도록 격리한다.

    두 겹으로 막는다:
    1) env 에서 GITHUB_TOKEN 을 제거한다.
    2) dotenv.load_dotenv 를 no-op 으로 만든다. main.py 는 런타임에 load_dotenv() 를
       호출하므로, AppTest.from_file("app/main.py") 가 main.py 를 재실행할 때마다 .env 의
       토큰이 os.environ 에 다시 주입되어 (1)을 무효화하고, load_settings/load_scores 가
       실제 GitHub 백엔드(프로덕션 scores-data 브랜치)로 빠진다. 이를 막지 않으면 테스트가
       프로덕션 데이터를 읽고 최악의 경우 쓴다.

    github 분기를 테스트하려면 각 테스트가 monkeypatch.setenv 로 명시적으로 토큰을 설정한다."""
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
