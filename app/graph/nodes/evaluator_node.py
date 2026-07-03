import logging

from app.graph.state import TeamState
from app.schemas.evaluation_schema import EvaluationSchema
from app.utils.compute_team_score_sum import compute_team_score_sum
from app.utils.build_evaluator_prompt import build_evaluator_prompt
from app.utils.group_members_by_score import group_members_by_score
from app.utils.validate_team_result import validate_team_result

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

    hard_validation = validate_team_result(
        members,
        team_a,
        team_b,
        must_link_groups,
        cannot_link_groups,
    )

    if hard_validation.status == "FAIL":
        message = f"'{evaluation_count + 1}번째' 검증 완료"
        logger.info(f"'{evaluation_count + 1}번째' 검증 중 ..")
        logger.info(message)
        logger.info(hard_validation)

        return {
            "messages": [message],
            "evaluation_status": hard_validation.status,
            "evaluation_reason": hard_validation.reason,
            "evaluation_count": evaluation_count + 1
        }

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
    final_evaluation = EvaluationSchema(
        status="PASS",
        reason=f"{hard_validation.reason}. {res.reason}",
    )

    message = f"'{evaluation_count + 1}번째' 검증 완료"
    logger.info(message)
    logger.info(final_evaluation)

    return {
        "messages": [message],
        "evaluation_status": final_evaluation.status,
        "evaluation_reason": final_evaluation.reason,
        "evaluation_count": evaluation_count + 1
    }
