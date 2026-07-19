import base64
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
BRANCH = "scores-data"
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


def _load_github_with_sha() -> tuple[dict, str]:
    """GitHub Contents API 로 scores.json 의 (파일 전체 dict, sha) 를 함께 읽어온다.
    settings 등 모르는 키까지 그대로 담아 반환하므로, save 시 read-modify-write 로
    형제 키를 보존할 수 있다. GET(읽기)과 PUT(쓰기)이 sha 를 공유해 409 를 감지한다."""
    resp = requests.get(
        f"{_API_BASE}/repos/{OWNER}/{REPO}/contents/{SCORES_PATH}",
        params={"ref": BRANCH},
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    try:
        raw = base64.b64decode(payload["content"]).decode("utf-8")
        return json.loads(raw), payload["sha"]
    except (KeyError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"scores.json 형식이 올바르지 않습니다: {e}"
        ) from e


def _load_github() -> dict:
    """GitHub 에서 파일 전체 dict 만 읽어온다 (sha 불필요 경로)."""
    data, _sha = _load_github_with_sha()
    return data


def _save_github(data: dict, sha: str | None = None) -> None:
    """GitHub Contents API 로 파일 전체 dict 를 갱신(새 커밋).
    sha 가 주어지면 재사용, 없으면 저장 직전 GET 으로 최신 sha 조회. GET→PUT 사이
    다른 쓰기가 끼면 동일 sha 로 409 Conflict 가 나 예외가 전파된다(단일 편집자 가정)."""
    if sha is None:
        get_resp = requests.get(
            f"{_API_BASE}/repos/{OWNER}/{REPO}/contents/{SCORES_PATH}",
            params={"ref": BRANCH},
            headers=_headers(),
            timeout=15,
        )
        get_resp.raise_for_status()
        sha = get_resp.json()["sha"]

    content = base64.b64encode(
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")

    put_resp = requests.put(
        f"{_API_BASE}/repos/{OWNER}/{REPO}/contents/{SCORES_PATH}",
        headers=_headers(),
        json={
            "message": COMMIT_MESSAGE,
            "content": content,
            "sha": sha,
            "branch": BRANCH,
        },
        timeout=15,
    )
    put_resp.raise_for_status()


def _project_root() -> Path:
    project_root = Path(__file__).resolve()

    # 루트까지 올라가기 (team-balancer 기준 찾기)
    while project_root.name != "team-balancer":
        project_root = project_root.parent

    return project_root


def _scores_path() -> Path:
    return _project_root() / "data" / "scores.json"


def _load_full() -> dict:
    """토큰 유무로 github/local 을 분기하는 읽기 전용 래퍼 (파일 전체 dict)."""
    if _get_token():
        return _load_github()
    return _load_local()


def load_scores() -> dict[str, int]:
    return _load_full().get("scores", {})


def _apply_delta(
    scores: dict[str, int],
    updates: dict[str, int] | None = None,
    deletes: set[str] | None = None,
) -> None:
    """scores 위에 upsert/delete 델타를 제자리(in-place) 적용."""
    if updates:
        scores.update(updates)
    if deletes:
        for name in deletes:
            scores.pop(name, None)


def save_scores(
    updates: dict[str, int] | None = None,
    deletes: set[str] | None = None,
) -> None:
    """파일 전체를 (재)읽어 scores 에만 델타를 적용하고 전체를 저장한다.
    settings 등 형제 키는 그대로 보존된다. GitHub 백엔드에선 읽어온 sha 를 재사용한다."""
    if _get_token():
        data, sha = _load_github_with_sha()
        _apply_delta(data.setdefault("scores", {}), updates, deletes)
        _save_github(data, sha=sha)
    else:
        try:
            data = _load_local()
        except FileNotFoundError:
            data = {}
        _apply_delta(data.setdefault("scores", {}), updates, deletes)
        _save_local(data)


def _load_local() -> dict:
    with open(_scores_path(), "r", encoding="utf-8") as f:
        return json.load(f)


def _save_local(data: dict) -> None:
    """파일 전체 dict 를 scores.json 에 원자적으로 기록한다.
    임시 파일에 쓴 뒤 os.replace 로 교체해 반쪽 파일이 남지 않게 한다."""
    path = _scores_path()
    tmp_path = path.with_suffix(".json.tmp")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    os.replace(tmp_path, path)
