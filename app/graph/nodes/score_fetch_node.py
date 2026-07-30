import logging

from app.graph.state import TeamState
from app.utils.load_scores import load_scores

logger = logging.getLogger("team_balancer")

def score_fetch_node(state: TeamState) -> TeamState:
    members = state["members"]
    default_score = state["default_score"]
    scores = load_scores()

    member_scores = {}
    member_score_sources = {}
    for member in members:
        if member in scores:
            member_scores[member] = scores[member]
            member_score_sources[member] = "registered"
        else:
            member_scores[member] = default_score
            member_score_sources[member] = "default"

    message = f"가중치 적용 완료"
    logger.info(message)

    return {
        "messages": [message],
        "member_scores": member_scores,
        "member_score_sources": member_score_sources,
        "score_source": "data/scores.json",
    }
