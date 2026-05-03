import json
from pathlib import Path
from app.graph.state import TeamState

def score_fetch_node(state: TeamState) -> TeamState:
    members = state["members"]
    scores = load_scores()
    
    member_scores = {}
    for member in members:
        member_scores[member] = scores.get(member, 3)

    message = f"가중치 적용 완료"

    print(message)

    return {
        "messages": [message],
        "member_scores": member_scores,
        "score_source": "data/scores.json",
    }

def load_scores():
    path = Path(__file__).resolve().parents[3] / "data" / "scores.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data["scores"]