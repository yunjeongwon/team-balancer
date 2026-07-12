# scores.json GitHub API 영속화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `data/scores.json`의 읽기/쓰기를 로컬 파일에서 GitHub Contents API(같은 repo)로 옮겨, Streamlit Community Cloud(ephemeral)에서도 점수 변경이 유지되도록 한다.

**Architecture:** `app/utils/load_scores.py`의 공개 함수(`load_scores`/`save_scores`) 시그니처는 유지하고 내부만 리팩터한다. `GITHUB_TOKEN` 유무로 로컬 파일 백엔드(`_load_local`/`_save_local`, 기존 로직)와 GitHub API 백엔드(`_load_github`/`_save_github`, 신규)를 자동 분기한다. CRUD 페이지·fetch 노드는 변경하지 않는다.

**Tech Stack:** Python 3.11, `requests`, GitHub REST Contents API, pytest, Streamlit.

## Global Constraints

- Python 3.11 (`pyproject.toml`의 `requires-python`)
- `data/scores.json`은 **git에 tracked로 유지** (gitignore 추가 금지). 이 파일이 API가 읽고 쓰는 원격 데이터.
- 로컬 토큰은 `.env`의 `GITHUB_TOKEN` (`.env`는 이미 gitignored).
- Cloud 토큰은 Streamlit Secrets의 `GITHUB_TOKEN`.
- 공개 시그니처 변경 금지: `load_scores() -> dict[str, int]`, `save_scores(scores: dict[str, int]) -> None`, `_scores_path() -> Path` (기존 테스트가 `_scores_path`를 monkeypatch함).
- 토큰 없으면 무조건 로컬 파일 분기 (자동). 로컬 변경이 Cloud에 반영되지 않는 건 감수.

## File Structure

- `app/utils/load_scores.py` (modify) — 백엔드 분기 + GitHub 헬퍼. 단일 책임: scores 영속성.
- `tests/test_scores_github.py` (create) — GitHub 백엔드 + 분기 로직 단위 테스트 (requests 모킹).
- `tests/test_save_scores.py` (unchanged, regression) — 로컬 백엔드 round-trip. 토큰 없으므로 자동 로컬 분기.
- `pyproject.toml` (modify) — `requests` 의존성 명시 추가.

---

## Task 1: `requests` 의존성 명시 추가

**Files:**
- Modify: `pyproject.toml` (`[project]` → `dependencies`)

**Interfaces:**
- Produces: `requests`가 명시 의존성으로 install 됨. 이후 Task에서 `import requests` 사용.

- [ ] **Step 1: `dependencies` 배열에 `requests` 추가**

`pyproject.toml`의 `dependencies`를 다음과 같이 변경 (알파벳 순 정렬 유지):

```toml
dependencies = [
    "langchain>=1.3.11",
    "langchain-anthropic>=1.4.8",
    "langchain-google-genai>=4.2.2",
    "langchain-openai>=1.2.1",
    "langgraph>=1.2.6",
    "python-dotenv>=1.2.2",
    "requests>=2.32",
    "streamlit>=1.57.0",
]
```

- [ ] **Step 2: 동기화 및 import 확인**

Run: `uv sync && uv run python -c "import requests; print(requests.__version__)"`
Expected: 버전 출력 (예: `2.33.1`), 에러 없음.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add requests as explicit dependency for GitHub API"
```

---

## Task 2: `_get_token` + 헤더 헬퍼

**Files:**
- Modify: `app/utils/load_scores.py` (import 블록 + 상수 + 헬퍼 추가)
- Test: `tests/test_scores_github.py` (create)

**Interfaces:**
- Produces: `_get_token() -> str | None` (env 우선, 없으면 st.secrets, 둘 다 없으면 None). `_headers() -> dict` (Authorization + Accept 헤더). 상수 `OWNER`, `REPO`, `SCORES_PATH`, `BRANCH`, `COMMIT_MESSAGE`, `_API_BASE`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_scores_github.py` 생성:

```python
from app.utils import load_scores as ls


def test_get_token_prefers_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    assert ls._get_token() == "env-token"


def test_get_token_returns_none_when_absent(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # 테스트 컨텍스트에선 st.secrets 도 unavailable → None
    assert ls._get_token() is None


def test_headers_includes_authorization_and_accept(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    h = ls._headers()
    assert h["Authorization"] == "token abc"
    assert h["Accept"] == "application/vnd.github+json"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_scores_github.py -v`
Expected: FAIL — `_get_token` / `_headers` 속성 없음 (AttributeError).

- [ ] **Step 3: 상수 + 헬퍼 구현**

`app/utils/load_scores.py` 상단(import 아래, `_project_root` 위)에 추가:

```python
import os

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
```

주의: 파일 상단의 기존 import(`json`, `os`, `Path`) 중 `os`가 이미 있으므로 중복 추가하지 말고 병합. `from dotenv import load_dotenv`와 `import requests`는 새로 추가.

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_scores_github.py -v`
Expected: 3 passed.

- [ ] **Step 5: 기존 테스트 회귀 확인**

Run: `uv run pytest tests/test_save_scores.py -v`
Expected: 4 passed. (아직 분기 도입 전이므로 영향 없음.)

- [ ] **Step 6: Commit**

```bash
git add app/utils/load_scores.py tests/test_scores_github.py
git commit -m "feat: add github token helper and api config"
```

---

## Task 3: `_load_github` (Contents API 읽기)

**Files:**
- Modify: `app/utils/load_scores.py` (`_load_github` 추가)
- Test: `tests/test_scores_github.py` (테스트 추가)

**Interfaces:**
- Consumes: `_headers()`, 상수들 (Task 2).
- Produces: `_load_github() -> dict[str, int]`.

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_scores_github.py` 상단에 helper와 테스트 추가:

```python
import base64
import json
from unittest.mock import MagicMock, patch

from app.utils import load_scores as ls


def _fake_contents_response(scores_dict, sha="abc123"):
    content = base64.b64encode(
        json.dumps({"scores": scores_dict}, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    return {"content": content, "sha": sha, "encoding": "base64"}


def test_get_token_prefers_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    assert ls._get_token() == "env-token"


def test_get_token_returns_none_when_absent(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert ls._get_token() is None


def test_headers_includes_authorization_and_accept(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    h = ls._headers()
    assert h["Authorization"] == "token abc"
    assert h["Accept"] == "application/vnd.github+json"


def test_load_github_decodes_base64_and_returns_scores(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    fake = _fake_contents_response({"alice": 5, "bob": 3})
    with patch.object(ls, "requests") as mock_req:
        mock_req.get.return_value = MagicMock(json=MagicMock(return_value=fake))
        result = ls._load_github()
    assert result == {"alice": 5, "bob": 3}
    # 올바른 URL 과 ref 파라미터 호출 검증
    _, kwargs = mock_req.get.call_args
    assert kwargs["params"] == {"ref": "master"}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_scores_github.py::test_load_github_decodes_base64_and_returns_scores -v`
Expected: FAIL — `_load_github` 없음.

- [ ] **Step 3: `_load_github` 구현**

`app/utils/load_scores.py`에 `_headers` 아래에 추가:

```python
def _load_github() -> dict[str, int]:
    """GitHub Contents API 로 scores.json 을 읽어 dict 로 반환."""
    resp = requests.get(
        f"{_API_BASE}/repos/{OWNER}/{REPO}/contents/{SCORES_PATH}",
        params={"ref": BRANCH},
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    raw = base64.b64decode(payload["content"]).decode("utf-8")
    return json.loads(raw)["scores"]
```

`base64`를 파일 상단 import에 추가 (`import base64`).

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_scores_github.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/utils/load_scores.py tests/test_scores_github.py
git commit -m "feat: add github contents api read backend"
```

---

## Task 4: `_save_github` (Contents API 쓰기, SHA 낙관적 락)

**Files:**
- Modify: `app/utils/load_scores.py` (`_save_github` 추가)
- Test: `tests/test_scores_github.py` (테스트 추가)

**Interfaces:**
- Consumes: `_headers()`, 상수들, `_API_BASE`.
- Produces: `_save_github(scores: dict[str, int]) -> None`. 흐름: GET 으로 최신 sha 조회 → base64 인코딩 → PUT (새 커밋).

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_scores_github.py`에 추가:

```python
def test_save_github_fetches_sha_then_puts(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    fake_get = _fake_contents_response({"alice": 5}, sha="sha-xyz")
    with patch.object(ls, "requests") as mock_req:
        mock_req.get.return_value = MagicMock(json=MagicMock(return_value=fake_get))
        mock_req.put.return_value = MagicMock(status_code=200)

        ls._save_github({"alice": 7})

    # 1) GET 호출 (sha 조회)
    assert mock_req.get.called

    # 2) PUT 호출 — 본문에 sha, branch, message, base64 content 포함
    _, kwargs = mock_req.put.call_args
    body = kwargs["json"]
    assert body["sha"] == "sha-xyz"
    assert body["branch"] == "master"
    assert body["message"] == "chore(scores): update via app"
    decoded = json.loads(base64.b64decode(body["content"]).decode("utf-8"))
    assert decoded == {"scores": {"alice": 7}}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_scores_github.py::test_save_github_fetches_sha_then_puts -v`
Expected: FAIL — `_save_github` 없음.

- [ ] **Step 3: `_save_github` 구현**

`app/utils/load_scores.py`에 `_load_github` 아래에 추가:

```python
def _save_github(scores: dict[str, int]) -> None:
    """GitHub Contents API 로 scores.json 을 갱신(새 커밋).
    저장 직전 GET 으로 최신 sha 를 조회해 낙관적 락에 사용한다."""
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_scores_github.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/utils/load_scores.py tests/test_scores_github.py
git commit -m "feat: add github contents api write backend with sha lock"
```

---

## Task 5: 토큰 유무 분기 + 로컬 백엔드 추출

**Files:**
- Modify: `app/utils/load_scores.py` (`load_scores`/`save_scores` 본문을 `_load_local`/`_save_local`로 추출, 분기 추가)
- Test: `tests/test_scores_github.py` (분기 테스트 추가), `tests/test_save_scores.py` (변경 없음, 회귀)

**Interfaces:**
- Consumes: `_get_token()`, `_load_github`, `_save_github` (Task 2-4).
- Produces: `load_scores()`/`save_scores()` 가 토큰 유무에 따라 백엔드를 선택. `_load_local`/`_save_local` 은 기존 파일 로직(원자적 쓰기)을 그대로 사용하며 `_scores_path()` 사용 유지.

- [ ] **Step 1: 실패하는 분기 테스트 추가**

`tests/test_scores_github.py`에 추가:

```python
def test_load_scores_uses_github_when_token_present(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    with patch.object(ls, "_load_github", return_value={"x": 1}) as gh, \
         patch.object(ls, "_load_local") as loc:
        assert ls.load_scores() == {"x": 1}
    assert gh.called and not loc.called


def test_load_scores_uses_local_when_no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch.object(ls, "_load_github") as gh, \
         patch.object(ls, "_load_local", return_value={"y": 2}) as loc:
        assert ls.load_scores() == {"y": 2}
    assert loc.called and not gh.called


def test_save_scores_uses_github_when_token_present(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    with patch.object(ls, "_save_github") as gh, \
         patch.object(ls, "_save_local") as loc:
        ls.save_scores({"x": 1})
    assert gh.called and not loc.called


def test_save_scores_uses_local_when_no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch.object(ls, "_save_github") as gh, \
         patch.object(ls, "_save_local") as loc:
        ls.save_scores({"y": 2})
    assert loc.called and not gh.called
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_scores_github.py -k "uses_" -v`
Expected: FAIL — `_load_local`/`_save_local` 없음.

- [ ] **Step 3: 분기 + 로컬 백엔드 추출 구현**

`app/utils/load_scores.py`의 기존 `load_scores`/`save_scores`를 아래로 교체 (본문은 `_load_local`/`_save_local`로 이동, `_scores_path` 호출 유지):

```python
def load_scores() -> dict[str, int]:
    if _get_token():
        return _load_github()
    return _load_local()


def save_scores(scores: dict[str, int]) -> None:
    if _get_token():
        _save_github(scores)
    else:
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
```

- [ ] **Step 4: 분기 테스트 통과 확인**

Run: `uv run pytest tests/test_scores_github.py -v`
Expected: 9 passed (5 기존 + 4 분기).

- [ ] **Step 5: 기존 로컬 테스트 회귀 확인 (중요)**

Run: `uv run pytest tests/test_save_scores.py -v`
Expected: 4 passed. (`_scores_path` monkeypatch가 `_load_local`/`_save_local`에 그대로 적용되어야 함. 토큰이 없으므로 로컬 분기.)

- [ ] **Step 6: 전체 테스트 회귀 확인**

Run: `uv run pytest -v`
Expected: 전체 PASS (기존 테스트 + 새 테스트).

- [ ] **Step 7: Commit**

```bash
git add app/utils/load_scores.py tests/test_scores_github.py
git commit -m "feat: branch scores persistence between local and github backends"
```

---

## Task 6: 로컬 수동 검증 (스모크)

**Files:** (변경 없음 — 검증만)

**Interfaces:** (N/A)

이 태스크는 코드 변경이 아니라, 실제 GitHub API 로 round-trip 이 작동하는지 로컬에서 확인한다. 토큰 발급이 선행되어야 한다.

- [ ] **Step 1: Fine-grained token 발급**

GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens:
- Resource owner: `yunjeongwon`
- Repository access: Only select repositories → `team-balancer`
- Permissions → Repository permissions → Contents: **Read and Write**
- 생성 후 토큰 복사.

- [ ] **Step 2: `.env` 에 토큰 추가**

`.env`에 한 줄 추가 (`.env`는 이미 gitignored):

```
GITHUB_TOKEN=<발급받은 토큰>
```

- [ ] **Step 3: round-trip 스크립트 실행**

Run:
```bash
uv run python -c "from app.utils.load_scores import load_scores, save_scores; \
s = load_scores(); print('loaded', len(s), 'players'); \
save_scores(s); print('re-saved (new commit)')"
```
Expected: `loaded 36 players` / `re-saved (new commit)` 출력, 에러 없음.

- [ ] **Step 4: GitHub 에 새 커밋 반영 확인**

Run: `git fetch && git log origin/master --oneline -3` 또는 GitHub 웹에서 `data/scores.json` history 확인.
Expected: `chore(scores): update via app` 커밋이 최상단에 추가됨.

- [ ] **Step 5: (선택) 로컬 파일 fallback 확인**

`GITHUB_TOKEN`을 임시로 unset 하고 로컬 분기 동작 확인:
```bash
unset GITHUB_TOKEN  # 현재 셸에서만
uv run python -c "from app.utils.load_scores import _get_token; print(_get_token())"
```
Expected: `None`. (이 상태에선 `_save_local` 로컬 파일에만 쓰고 GitHub 에 커밋하지 않음 — 기대 동작.)

- [ ] **Step 6: Commit**

코드 변경이 없으므로 커밋 생략. 다음 배포/Cloud secrets 설정으로 진행.

---

## Cloud 배포 후 검증 (Plan 범위 밖, 참고용)

Streamlit Cloud Secrets 에 `GITHUB_TOKEN` 추가 후 재배포 → 점수 관리 페이지에서 CRUD → 페이지 새로고침/앱 재시작 후에도 데이터 유지 확인. 이 단계는 사용자가 Cloud 대시보드에서 수동 수행.
