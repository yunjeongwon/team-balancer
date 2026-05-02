import json
from pathlib import Path
from app.graph.state import TeamState

def score_fetch_node(state: TeamState) -> TeamState:
    members = state["members"]
    scores = load_scores()
    
    member_scores = {}
    for member in members:
        member_scores[member] = scores.get(member, 3)

    return {
        "member_scores": member_scores,
        "score_source": "data/scores.json",
    }

def load_scores():
    path = Path(__file__).resolve().parents[3] / "data" / "scores.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data["scores"]