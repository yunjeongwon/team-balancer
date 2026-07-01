import logging

from langgraph.types import interrupt
from app.graph.state import TeamState

logger = logging.getLogger("team_balancer")


def human_approval_node(state: TeamState) -> TeamState:
    feedback = interrupt(
        {
            "message": "수정 요청을 입력해주세요.",
            "team_a": state["team_a"],
            "team_b": state["team_b"],
        }
    )

    message = f"수정 요청 입력"
    logger.info(message)

    return {
        "messages": [message],
        "feedback": feedback,
        "evaluation_count": 0
    }