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
