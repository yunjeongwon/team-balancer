import logging

from app.exceptions.validation import ValidationError
from app.graph.state import TeamState
from app.utils.build_balanced_teams import build_balanced_teams
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

    logger.info("팀 생성 중 ..")

    if feedback:
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

        res = structured_llm.invoke(prompt)
        generated_team_a = res.team_a
        generated_team_b = res.team_b
        output_reason = res.reason
    else:
        try:
            res = build_balanced_teams(
                members=members,
                member_scores=member_scores,
                must_link_groups=must_link_groups,
                cannot_link_groups=cannot_link_groups,
            )
        except ValueError as error:
            raise ValidationError(str(error)) from error

        generated_team_a = res.team_a
        generated_team_b = res.team_b
        output_reason = res.reason

    team_a_score_sum = sum(member_scores.get(member, 0) for member in generated_team_a)
    team_b_score_sum = sum(member_scores.get(member, 0) for member in generated_team_b)

    message = f"팀 생성 완료"
    logger.info(message)
    logger.info(f"res========= {res}")

    return {
        "messages": [message],
        "team_a": generated_team_a,
        "team_b": generated_team_b,
        "score_diff": abs(team_a_score_sum - team_b_score_sum),
        "output_reason": output_reason,
    }
