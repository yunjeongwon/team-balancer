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
