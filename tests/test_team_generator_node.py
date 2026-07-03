from app.schemas.team_schema import TeamSchema
from app.utils.validate_team_result import validate_team_result
import app.graph.builder as builder_mod


def test_initial_generation_builds_valid_teams_without_team_llm(fake_llm):
    app = builder_mod.graph_builder()
    config = {"configurable": {"thread_id": "t1"}}
    app.invoke(
        {
            "members_input": (
                "강병의 김성인 김형욱 박규원 박종민 선윤호 양창온 윤성빈 장진석 "
                "정재훈 조환준 최한성 정윤재 박찬준 권순우 웜뱃 셋텟난뉘 세훈"
            ),
            "must_link_groups_input": "박규원-박종민",
            "cannot_link_groups_input": "박종민/권순우, 조환준/김성인",
            "default_score": 4,
        },
        config=config,
    )

    snapshot = app.get_state(config)
    values = snapshot.values
    validation = validate_team_result(
        members=values["members"],
        team_a=values["team_a"],
        team_b=values["team_b"],
        must_link_groups=values["must_link_groups"],
        cannot_link_groups=values["cannot_link_groups"],
    )

    assert fake_llm.team_prompts == []
    assert validation.status == "PASS"
    assert len(values["team_a"]) == 9
    assert len(values["team_b"]) == 9
    assert values["score_diff"] == 1


def test_evaluator_prompt_includes_computed_team_score_sums(fake_llm):
    app = builder_mod.graph_builder()
    config = {"configurable": {"thread_id": "t2"}}
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


def test_generated_score_diff_is_recomputed_from_member_scores(fake_llm):
    fake_llm.team_responses = [
        TeamSchema(team_a=["a"], team_b=["b"], score_diff=999, reason="bad diff"),
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

    snapshot = app.get_state(config)
    assert snapshot.values["score_diff"] == 0
