import json
import os
from pathlib import Path


def _project_root() -> Path:
    project_root = Path(__file__).resolve()

    # 루트까지 올라가기 (team-balancer 기준 찾기)
    while project_root.name != "team-balancer":
        project_root = project_root.parent

    return project_root


def _scores_path() -> Path:
    return _project_root() / "data" / "scores.json"


def load_scores() -> dict[str, int]:
    with open(_scores_path(), "r", encoding="utf-8") as f:
        data = json.load(f)

    return data["scores"]


def save_scores(scores: dict[str, int]) -> None:
    """{"scores": {...}} 래퍼 구조를 보존하여 scores.json에 원자적으로 기록한다.
    임시 파일에 쓴 뒤 os.replace 로 교체해, 쓰기 도중 실패해도 반쪽 파일이
    남지 않도록 한다."""
    path = _scores_path()
    tmp_path = path.with_suffix(".json.tmp")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"scores": scores}, f, ensure_ascii=False, indent=4)

    os.replace(tmp_path, path)
