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
