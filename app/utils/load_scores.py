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


def _load_github_with_sha() -> tuple[dict[str, int], str]:
    """GitHub Contents API 로 scores.json 의 (내용, sha) 를 한 번에 읽어온다.

    save_scores 가 이 sha 를 PUT 에 그대로 재사용하도록 content 와 sha 를
    같은 응답에서 얻는다 — GET(읽기) 과 PUT(쓰기) 가 sha 를 공유해야 그 사이에
    다른 쓰기가 끼어든 것을 409 로 잡을 수 있다.

    참고: 토큰이 설정된 배포 환경에서는 매 저장마다 api.github.com 으로 네트워크
    GET 을 보낸다. GitHub API 장애/속도제한이 점수 저장에 직접 영향을 미친다
    (로컬 폴백 없음 — ephemeral FS 가 그 이유)."""
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
        return json.loads(raw)["scores"], payload["sha"]
    except (KeyError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"scores.json 형식이 올바르지 않습니다: {e}"
        ) from e


def _load_github() -> dict[str, int]:
    """GitHub 에서 scores 만 읽어온다 (sha 가 필요 없는 읽기 전용 경로)."""
    scores, _sha = _load_github_with_sha()
    return scores


def _save_github(scores: dict[str, int], sha: str | None = None) -> None:
    """GitHub Contents API 로 scores.json 을 갱신(새 커밋).

    sha 가 주어지면 그것을 그대로 쓰고, 없으면 저장 직전 GET 으로 최신 sha 를
    조회한다. save_scores 는 읽어온 sha 를 재사용해 전달하므로, GET→PUT 사이에
    다른 쓰기가 끼면 동일한 sha 로 인해 PUT 시 HTTP 409 Conflict 로 나타난다
    (단일 편집자 가정). 그 경우 예외가 전파된다."""
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
        json.dumps({"scores": scores}, ensure_ascii=False).encode("utf-8")
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


def load_scores() -> dict[str, int]:
    if _get_token():
        return _load_github()
    return _load_local()


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
    """최신 scores 를 (재)읽어와 델타(updates/deletes) 만 적용한 뒤 저장한다.

    페이지 로드 시점의 낡은 스냅샷을 통째로 덮어쓰는 대신, 저장 직전 최신 상태에
    델타만 얹는다(read-modify-write). GitHub 백엔드에선 읽어온 sha 를 PUT 에
    재사용해 다른 사람의 동시 편집을 덮어쓰지 않도록 한다."""
    if _get_token():
        scores, sha = _load_github_with_sha()
        _apply_delta(scores, updates, deletes)
        _save_github(scores, sha=sha)
    else:
        try:
            scores = _load_local()
        except FileNotFoundError:
            scores = {}
        _apply_delta(scores, updates, deletes)
        _save_local(scores)


def _load_local() -> dict[str, int]:
    with open(_scores_path(), "r", encoding="utf-8") as f:
        data = json.load(f)

    return data["scores"]


def _save_local(scores: dict[str, int]) -> None:
    """{"scores": {...}} 래퍼 구조를 보존하여 scores.json에 원자적으로 기록한다.
    임시 파일에 쓴 뒤 os.replace 로 교체해, 쓰기 도중 실패해도 반쪽 파일이
    남지 않도록 한다."""
    path = _scores_path()
    tmp_path = path.with_suffix(".json.tmp")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"scores": scores}, f, ensure_ascii=False, indent=4)

    os.replace(tmp_path, path)
