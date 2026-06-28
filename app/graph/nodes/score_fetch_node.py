from app.graph.state import TeamState
from app.utils.load_scores import load_scores

def score_fetch_node(state: TeamState) -> TeamState:
    members = state["members"]
    default_score = state["default_score"]
    scores = load_scores()

    member_scores = {}
    for member in members:
        member_scores[member] = scores.get(member, default_score)

    message = f"가중치 적용 완료"
    print(message)

    return {
        "messages": [message],
        "member_scores": member_scores,
        "score_source": "data/scores.json",
    }

