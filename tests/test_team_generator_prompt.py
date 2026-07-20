from app.utils.build_team_generator_base_prompt_section import (
    build_team_generator_prompt,
)


def test_base_prompt_avoids_hardcoded_score_scale():
    prompt = build_team_generator_prompt(
        score_groups={7: ["a"], 1: ["b"]},
        must_link_groups=[],
        cannot_link_groups=[],
        feedback=None,
        team_a=None,
        team_b=None,
    )
    human = prompt[-1].content
    assert "극단 점수대" in human
    assert "2점 이하" not in human
    assert "5점 이상" not in human
