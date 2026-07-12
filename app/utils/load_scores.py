import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# --- GitHub 백엔드 설정 ---
OWNER = "yunjeongwon"
REPO = "team-balancer"
SCORES_PATH = "data/scores.json"
BRANCH = "master"
COMMIT_MESSAGE = "chore(scores): update via app"
_API_BASE = "https://api.github.com"


def _get_token() -> str | None:
    """GITHUB_TOKEN 을 환경변수 우선, 없으면 Streamlit Secrets 에서 읽는다.
    둘 다 없으면 None. app/auth.py 의 APP_PASSWORD 패턴과 동일."""
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        import streamlit as st

        return st.secrets.get("GITHUB_TOKEN") or None
    except Exception:
        # streamlit 미구동 또는 secrets 미설정
        return None


def _headers() -> dict:
    return {
        "Authorization": f"token {_get_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


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
