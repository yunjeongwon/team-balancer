import json
from pathlib import Path

def load_scores():
    project_root = Path(__file__).resolve()

    # 루트까지 올라가기 (team-balancer 기준 찾기)
    while project_root.name != "team-balancer":
        project_root = project_root.parent

    path = project_root / "data" / "scores.json"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data["scores"]