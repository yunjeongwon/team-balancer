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
