# 기본 점수 / 최고 점수 설정화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 점수 미등록자에게 매기는 `default_score`와 점수 입력 상한 `max_score`를 코드 하드코딩에서 `scores.json`의 `settings` 블록으로 옮겨, 점수 관리 페이지에서 편집 가능하게 한다.

**Architecture:** `scores.json`을 `{"scores": {...}, "settings": {default_score, max_score}}` 구조로 확장한다. `load_scores.py`의 내부 표현을 "scores 딕셔너리"에서 "파일 전체 딕셔너리"로 바꿔, 어떤 형제 키(settings 등)도 read-modify-write 중 보존되게 한다(GitHub 백엔드의 형제 키 소실 함정 제거). `default_score`는 `main.py`가 저장소에서 읽어 그래프 state로 주입하고, `max_score`는 점수 관리 페이지의 입력 검증 상한으로만 쓴다.

**Tech Stack:** Python, Streamlit(`st.data_editor`, `st.form`, `AppTest`), LangGraph, GitHub Contents API, pytest.

## Global Constraints

- 폴백 상수(verbatim): `DEFAULT_SCORE = 3`, `MAX_SCORE = 7` (`app/constants.py`).
- 파일 구조(verbatim): `{"scores": {"<이름>": <int>}, "settings": {"default_score": <int>, "max_score": <int>}}`.
- `load_scores.py` 내부 헬퍼는 **파일 전체 dict**를 다룬다. 모든 공개 함수는 전체 파일 단위 read-modify-write를 수행해 서로의 키를 보존한다.
- GitHub 백엔드: 읽어온 `sha`를 PUT에 재사용해 동시 편집을 409로 감지(단일 편집자 가정). 이 동작을 유지한다.
- 그래프(`state.py`, `score_fetch_node.py`, `builder.py`)는 **변경하지 않는다.** `default_score` 주입 지점은 `main.py` 한 곳.
- Git: `master`에 직접 커밋. push는 사용자 확인 후. 브랜치/PR 없음.
- 테스트: 실제 LLM 금지. `tests/conftest.py`의 `RecordingFakeLLM`/`fake_llm` 픽스처 사용.
- 베이스라인: `uv run pytest -q` → `54 passed`.

---

### Task 1a: `load_scores.py` — 전체 payload 리팩터 (scores 동작 불변)

내부 헬퍼의 반환 계약을 "scores dict"에서 "파일 전체 dict"로 바꾼다. `load_scores`/`save_scores`의 **외부 동작은 그대로**(scores in, scores out) 유지하고, 이 계약 변화를 검증하는 기존 GitHub 테스트 4개를 새 계약에 맞춘다. settings 기능은 Task 1b에서 얹는다.

**Files:**
- Modify: `app/utils/load_scores.py:43-183`
- Test: `tests/test_scores_github.py` (기존 4개 수정), `tests/test_save_scores.py` (수정 없음, 회귀 확인용)

**Interfaces:**
- Produces:
  - `_load_github_with_sha() -> tuple[dict, str]` — (파일 전체 dict, sha)
  - `_load_github() -> dict` — 파일 전체 dict
  - `_save_github(data: dict, sha: str | None = None) -> None` — 파일 전체 dict 저장
  - `_load_local() -> dict` — 파일 전체 dict (부재 시 `FileNotFoundError`)
  - `_save_local(data: dict) -> None` — 파일 전체 dict 원자적 저장
  - `_load_full() -> dict` — 토큰 유무로 github/local 분기하는 읽기 래퍼
  - `load_scores() -> dict[str, int]` — 시그니처·의미 불변 (scores만 반환)
  - `save_scores(updates=None, deletes=None) -> None` — 시그니처·의미 불변

- [ ] **Step 1: 기존 GitHub 테스트 4개를 새 계약으로 수정 (RED)**

`tests/test_scores_github.py`에서 아래 4개 테스트를 교체한다.

`test_load_github_decodes_base64_and_returns_scores` → 이름/본문 교체:

```python
def test_load_github_returns_full_payload(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    fake = _fake_contents_response({"alice": 5, "bob": 3})
    with patch.object(ls, "requests") as mock_req:
        mock_req.get.return_value = MagicMock(json=MagicMock(return_value=fake))
        result = ls._load_github()
    assert result == {"scores": {"alice": 5, "bob": 3}}
    _, kwargs = mock_req.get.call_args
    assert kwargs["params"] == {"ref": "scores-data"}
```

`test_save_github_fetches_sha_then_puts` → 호출 인자를 전체 dict로:

```python
        ls._save_github({"scores": {"alice": 7}})
```
(같은 테스트의 `decoded == {"scores": {"alice": 7}}` 단언은 그대로 둔다.)

`test_load_scores_uses_github_when_token_present` → 패치 반환값을 전체 dict로:

```python
def test_load_scores_uses_github_when_token_present(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    with patch.object(ls, "_load_github", return_value={"scores": {"x": 1}}) as gh, \
         patch.object(ls, "_load_local") as loc:
        assert ls.load_scores() == {"x": 1}
    assert gh.called and not loc.called
```

`test_load_scores_uses_local_when_no_token` → 패치 반환값을 전체 dict로:

```python
def test_load_scores_uses_local_when_no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch.object(ls, "_load_github") as gh, \
         patch.object(ls, "_load_local", return_value={"scores": {"y": 2}}) as loc:
        assert ls.load_scores() == {"y": 2}
    assert loc.called and not gh.called
```

- [ ] **Step 2: 테스트가 실패하는지 확인 (RED)**

Run: `uv run pytest tests/test_scores_github.py -q`
Expected: FAIL — `test_load_github_returns_full_payload`가 `{"alice": 5, "bob": 3}`(구현이 아직 scores만 반환)로 실패, 나머지도 계약 불일치로 실패.

- [ ] **Step 3: `load_scores.py` 내부 헬퍼와 공개 함수 리팩터 (GREEN)**

`app/utils/load_scores.py`의 `_load_github_with_sha`부터 파일 끝까지(현재 43~183행)를 아래로 교체한다. `_apply_delta`, `_project_root`, `_scores_path`, 상수/`_get_token`/`_headers`는 그대로 둔다.

```python
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
```

- [ ] **Step 4: 관련 테스트 통과 확인 (GREEN)**

Run: `uv run pytest tests/test_scores_github.py tests/test_save_scores.py -q`
Expected: PASS (전부). `test_save_scores.py`는 수정 없이 통과해야 한다 — `{"scores": {...}}` 래퍼가 보존되기 때문.

- [ ] **Step 5: 전체 스위트 회귀 확인**

Run: `uv run pytest -q`
Expected: `54 passed` (동작 불변 리팩터).

- [ ] **Step 6: 커밋**

```bash
git add app/utils/load_scores.py tests/test_scores_github.py
git commit -m "$(cat <<'EOF'
refactor(scores): load_scores 내부 표현을 파일 전체 dict로 전환

형제 키(settings 등)를 read-modify-write 중 보존하도록 내부 헬퍼가
scores 딕셔너리 대신 파일 전체 dict를 다루게 한다. load_scores/save_scores
외부 동작은 불변.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 1b: `load_settings` / `save_settings` + 폴백 상수

Task 1a의 전체 payload 기반 위에 settings 읽기/쓰기를 얹는다.

**Files:**
- Modify: `app/constants.py:1`
- Modify: `app/utils/load_scores.py` (import 추가 + 함수 2개 추가)
- Test: `tests/test_settings.py` (신규)

**Interfaces:**
- Consumes: `_load_full`, `_load_github_with_sha`, `_load_local`, `_save_github`, `_save_local`, `_get_token` (Task 1a)
- Produces:
  - `app.constants.DEFAULT_SCORE = 3`, `app.constants.MAX_SCORE = 7`
  - `load_settings() -> dict` — `{"default_score": int, "max_score": int}`, 부재 키/부재 파일은 상수 폴백
  - `save_settings(default_score: int, max_score: int) -> None` — settings 만 교체, scores 보존

- [ ] **Step 1: 실패 테스트 작성 (RED)**

`tests/test_settings.py` 신규 작성:

```python
import base64
import json
from unittest.mock import MagicMock, patch

from app.constants import DEFAULT_SCORE, MAX_SCORE
from app.utils import load_scores as ls


def test_load_settings_falls_back_to_constants_when_absent(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(json.dumps({"scores": {"김": 5}}), encoding="utf-8")
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    assert ls.load_settings() == {"default_score": DEFAULT_SCORE, "max_score": MAX_SCORE}


def test_load_settings_partial_falls_back_per_key(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(
        json.dumps({"scores": {}, "settings": {"default_score": 2}}), encoding="utf-8"
    )
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    assert ls.load_settings() == {"default_score": 2, "max_score": MAX_SCORE}


def test_load_settings_missing_file_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "_scores_path", lambda: tmp_path / "nope.json")

    assert ls.load_settings() == {"default_score": DEFAULT_SCORE, "max_score": MAX_SCORE}


def test_save_settings_local_preserves_scores(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(json.dumps({"scores": {"김": 5}}), encoding="utf-8")
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_settings(default_score=3, max_score=7)

    raw = json.loads(fake_path.read_text(encoding="utf-8"))
    assert raw == {"scores": {"김": 5}, "settings": {"default_score": 3, "max_score": 7}}


def test_save_scores_local_preserves_settings(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(
        json.dumps(
            {"scores": {"김": 5}, "settings": {"default_score": 3, "max_score": 7}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_scores(updates={"이": 2})

    raw = json.loads(fake_path.read_text(encoding="utf-8"))
    assert raw["settings"] == {"default_score": 3, "max_score": 7}
    assert raw["scores"] == {"김": 5, "이": 2}


def test_save_scores_github_preserves_settings(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    full = {"scores": {"alice": 5}, "settings": {"default_score": 3, "max_score": 7}}
    content = base64.b64encode(
        json.dumps(full, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    fake = {"content": content, "sha": "sha-1", "encoding": "base64"}
    with patch.object(ls, "requests") as mock_req:
        mock_req.get.return_value = MagicMock(json=MagicMock(return_value=fake))
        mock_req.put.return_value = MagicMock(status_code=200)
        ls.save_scores(updates={"bob": 2})

    _, kwargs = mock_req.put.call_args
    decoded = json.loads(base64.b64decode(kwargs["json"]["content"]).decode("utf-8"))
    assert decoded["settings"] == {"default_score": 3, "max_score": 7}
    assert decoded["scores"] == {"alice": 5, "bob": 2}
```

- [ ] **Step 2: 실패 확인 (RED)**

Run: `uv run pytest tests/test_settings.py -q`
Expected: FAIL — `ImportError: cannot import name 'DEFAULT_SCORE'` (constants 미정의) 및 `AttributeError: ... load_settings`.

- [ ] **Step 3: 상수 추가**

`app/constants.py` 를 아래로 만든다 (기존 1행 유지 + 2행 추가):

```python
PLACEHOLDER_MEMBER = "(공석)"
DEFAULT_SCORE = 3
MAX_SCORE = 7
```

- [ ] **Step 4: `load_settings` / `save_settings` 추가**

`app/utils/load_scores.py` 상단 import 블록에 상수 import 추가:

```python
from app.constants import DEFAULT_SCORE, MAX_SCORE
```

그리고 `load_scores` 정의 바로 아래에 두 함수를 추가한다:

```python
def load_settings() -> dict:
    """{"default_score": int, "max_score": int} 반환. 파일/키 부재 시 상수 폴백."""
    try:
        settings = _load_full().get("settings", {})
    except FileNotFoundError:
        settings = {}
    return {
        "default_score": settings.get("default_score", DEFAULT_SCORE),
        "max_score": settings.get("max_score", MAX_SCORE),
    }


def save_settings(default_score: int, max_score: int) -> None:
    """파일 전체를 (재)읽어 settings 만 교체하고 저장한다. scores 등은 보존된다."""
    settings = {"default_score": default_score, "max_score": max_score}
    if _get_token():
        data, sha = _load_github_with_sha()
        data["settings"] = settings
        _save_github(data, sha=sha)
    else:
        try:
            data = _load_local()
        except FileNotFoundError:
            data = {}
        data["settings"] = settings
        _save_local(data)
```

- [ ] **Step 5: 통과 확인 (GREEN)**

Run: `uv run pytest tests/test_settings.py -q`
Expected: `6 passed`.

- [ ] **Step 6: 전체 스위트 확인**

Run: `uv run pytest -q`
Expected: `60 passed`.

- [ ] **Step 7: 커밋**

```bash
git add app/constants.py app/utils/load_scores.py tests/test_settings.py
git commit -m "$(cat <<'EOF'
feat(scores): load_settings/save_settings 및 default/max 폴백 상수 추가

settings 블록을 scores.json에 형제 키로 읽고 쓴다. 부재 시 DEFAULT_SCORE=3,
MAX_SCORE=7로 폴백. save_settings/save_scores가 서로의 키를 보존한다.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `main.py` — `default_score` 를 저장소에서 주입

하드코딩 `"default_score": 4` 를 `load_settings()["default_score"]` 로 바꾼다.

**Files:**
- Modify: `app/main.py:10-16`(import), `app/main.py:152`
- Test: `tests/test_main_app.py` (미등록 멤버 점수 단언 4→3)

**Interfaces:**
- Consumes: `load_settings` (Task 1b)

- [ ] **Step 1: 기존 단언을 새 기본값(3)으로 수정 (RED)**

`tests/test_main_app.py` `test_generated_result_shows_member_scores_and_team_totals` 의 85~89행을 교체:

```python
    assert "🔵 블루팀 (총점: 3)" in rendered
    assert "🟡 골드팀 (총점: 3)" in rendered
    assert "a(3)" in rendered
    assert "b(3)" in rendered
    assert "3점" not in rendered
```

`test_confirm_adds_scoreless_result_without_changing_previous_message` 의 101~106행을 교체:

```python
    assert "총점: 3" in at.chat_message[-2].markdown[0].value
    assert "a(3)" in at.chat_message[-2].markdown[0].value

    rendered = at.chat_message[-1].markdown[0].value
    assert "총점" not in rendered
    assert "(3)" not in rendered
```

> 참고: 이 테스트들은 미등록 멤버 `a`/`b`가 `default_score`를 받는 동작을 검증한다. 실제 `data/scores.json`에는 `settings`가 없어 `load_settings()`가 상수 `DEFAULT_SCORE=3`으로 폴백하므로 값이 3이다.

- [ ] **Step 2: 실패 확인 (RED)**

Run: `uv run pytest tests/test_main_app.py -q`
Expected: FAIL — `main.py`가 아직 4를 주입해 `총점: 3`/`a(3)` 단언이 실패.

- [ ] **Step 3: `main.py` 수정 (GREEN)**

import 블록(현재 13행 부근, `from app.graph.builder import graph_builder` 아래)에 추가:

```python
from app.utils.load_scores import load_settings
```

`app/main.py:152` 를 교체:

```python
                    "default_score": load_settings()["default_score"],
```

- [ ] **Step 4: 통과 확인 (GREEN)**

Run: `uv run pytest tests/test_main_app.py -q`
Expected: PASS (전부).

- [ ] **Step 5: 전체 스위트 확인**

Run: `uv run pytest -q`
Expected: `60 passed`.

- [ ] **Step 6: 커밋**

```bash
git add app/main.py tests/test_main_app.py
git commit -m "$(cat <<'EOF'
feat(main): default_score를 하드코딩 대신 load_settings에서 주입

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3a: 점수 관리 페이지 — `max_score` 배선 + 프리필을 `default_score`로

페이지가 `load_settings()`를 읽어 캡션·입력 상한·추가 프리필에 반영하게 한다. "기본 설정" 편집 UI는 Task 3b.

**Files:**
- Modify: `app/pages/2_점수_관리.py:13`(import), `:15-21`(settings 읽기+캡션), `:47`(add 폼), `:84-86`(data_editor)
- Test: `tests/test_score_page.py` (프리필 4→3 단언 수정)

**Interfaces:**
- Consumes: `load_settings` (Task 1b)

- [ ] **Step 1: 기존 페이지 테스트의 프리필 단언을 3으로 수정 (RED)**

`tests/test_score_page.py`:

59행 주석과 64행:
```python
    at.text_input[0].set_value("신규").run()  # 점수는 기본값 3(=default_score)
```
```python
    assert saved == {"김동영": 7, "신규": 3}
```

71행:
```python
    assert at.session_state["pending_adds"] == [{"이름": "신규", "점수": 3}]
```

86행, 99행 (둘 다 동일 문자열):
```python
    assert at.session_state["pending_adds"] == [{"이름": "신규", "점수": 3}]
```

- [ ] **Step 2: 실패 확인 (RED)**

Run: `uv run pytest tests/test_score_page.py -q`
Expected: FAIL — 페이지가 아직 `value=4`라 프리필이 4로 남아 3 단언이 실패.

- [ ] **Step 3: 페이지 배선 수정 (GREEN)**

import (13행) 교체:
```python
from app.utils.load_scores import load_scores, load_settings, save_scores
```

`require_auth()` (15행) 바로 아래에 settings 읽기를 추가하고, 캡션을 f-string으로 바꾼다. 현재 15~21행을:

```python
require_auth()

st.title("점수 관리")
st.caption(
    "선수 이름과 실력 점수(1~7)를 관리합니다. 점수 셀을 눌러 수정하고, 삭제할 선수는 "
    "삭제 열을 체크한 뒤 저장하세요. 표 헤더(이름/점수)를 클릭하면 정렬됩니다."
)
```

아래로 교체:

```python
require_auth()

_settings = load_settings()
default_score = _settings["default_score"]
max_score = _settings["max_score"]

st.title("점수 관리")
st.caption(
    f"선수 이름과 실력 점수(1~{max_score})를 관리합니다. 점수 셀을 눌러 수정하고, 삭제할 선수는 "
    "삭제 열을 체크한 뒤 저장하세요. 표 헤더(이름/점수)를 클릭하면 정렬됩니다."
)
```

add 폼 number_input (현재 47행) 교체:

```python
        new_score = st.number_input(
            "점수", min_value=1, max_value=max_score, value=default_score, step=1
        )
```

data_editor 점수 컬럼 (현재 84~86행) 교체:

```python
        "점수": st.column_config.NumberColumn(
            "점수", min_value=1, max_value=max_score, step=1, format="%d", required=True
        ),
```

- [ ] **Step 4: 통과 확인 (GREEN)**

Run: `uv run pytest tests/test_score_page.py -q`
Expected: PASS (전부).

- [ ] **Step 5: 전체 스위트 확인**

Run: `uv run pytest -q`
Expected: `60 passed`.

- [ ] **Step 6: 커밋**

```bash
git add app/pages/2_점수_관리.py tests/test_score_page.py
git commit -m "$(cat <<'EOF'
feat(scores-page): 캡션·입력 상한을 max_score로, 추가 프리필을 default_score로

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3b: 점수 관리 페이지 — "기본 설정" 편집 UI

`default_score`/`max_score`를 편집·저장하는 접이식 섹션을 추가한다.

**Files:**
- Modify: `app/pages/2_점수_관리.py` ("선수 추가" expander 아래에 블록 추가, import에 `save_settings`)
- Test: `tests/test_score_page.py` (신규 3개)

**Interfaces:**
- Consumes: `save_settings` (Task 1b), `default_score`/`max_score`/`scores` (페이지 지역 변수)

- [ ] **Step 1: 실패 테스트 작성 (RED)**

`tests/test_score_page.py` 상단 헬퍼 아래에 추가:

```python
def _num(at, key):
    return next(n for n in at.number_input if n.key == key)
```

그리고 파일 끝에 테스트 3개 추가:

```python
def test_settings_save_persists(tmp_path, monkeypatch):
    fake_path = _seed(tmp_path, monkeypatch, {"김동영": 7})
    at = AppTest.from_file(PAGE)
    at.session_state["authenticated"] = True
    at.run()

    _num(at, "default_score_input").set_value(2).run()
    _num(at, "max_score_input").set_value(6).run()
    _button(at, "설정 저장").click().run()

    raw = json.loads(fake_path.read_text(encoding="utf-8"))
    assert raw["settings"] == {"default_score": 2, "max_score": 6}
    assert raw["scores"] == {"김동영": 7}  # scores 보존


def test_settings_rejects_default_above_max(tmp_path, monkeypatch):
    fake_path = _seed(tmp_path, monkeypatch, {"김동영": 7})
    at = AppTest.from_file(PAGE)
    at.session_state["authenticated"] = True
    at.run()

    _num(at, "max_score_input").set_value(2).run()
    _num(at, "default_score_input").set_value(5).run()
    _button(at, "설정 저장").click().run()

    assert any("기본 점수는 최고 점수보다" in e.value for e in at.error)
    raw = json.loads(fake_path.read_text(encoding="utf-8"))
    assert "settings" not in raw  # 저장되지 않음


def test_number_inputs_reflect_stored_settings(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(
        json.dumps(
            {"scores": {"김동영": 5}, "settings": {"default_score": 3, "max_score": 5}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)
    at = AppTest.from_file(PAGE)
    at.session_state["authenticated"] = True
    at.run()

    assert _num(at, "default_score_input").value == 3
    assert _num(at, "max_score_input").value == 5
```

- [ ] **Step 2: 실패 확인 (RED)**

Run: `uv run pytest tests/test_score_page.py -q`
Expected: FAIL — `설정 저장` 버튼/`default_score_input` 키가 없어 `StopIteration`/조회 실패.

- [ ] **Step 3: import에 `save_settings` 추가**

`app/pages/2_점수_관리.py` 13행 교체:

```python
from app.utils.load_scores import load_scores, load_settings, save_scores, save_settings
```

- [ ] **Step 4: "기본 설정" expander 추가 (GREEN)**

"선수 추가" expander 블록 바로 아래(추가 폼 처리 `st.rerun()` 다음, "편집 표" 주석 앞)에 추가:

```python
# --- 기본 설정: 미등록자 기본 점수 / 최고 점수 (즉시 저장) ---
with st.expander("기본 설정"):
    with st.form("settings_form"):
        default_input = st.number_input(
            "미등록 인원에게 적용할 점수",
            min_value=1, max_value=max_score, value=default_score, step=1,
            key="default_score_input",
        )
        max_input = st.number_input(
            "최고 점수",
            min_value=1, max_value=20, value=max_score, step=1,
            key="max_score_input",
        )
        settings_submitted = st.form_submit_button("설정 저장", type="primary")

    if settings_submitted:
        if default_input > max_input:
            st.error("기본 점수는 최고 점수보다 클 수 없습니다.")
        else:
            over = sorted(n for n, s in scores.items() if s > max_input)
            try:
                save_settings(
                    default_score=int(default_input), max_score=int(max_input)
                )
            except Exception as e:
                st.error(f"저장 중 오류가 발생했습니다: {e}")
            else:
                msg = f"설정이 저장되었습니다. (기본 {int(default_input)} · 최고 {int(max_input)})"
                if over:
                    msg += (
                        f" ⚠️ {len(over)}명이 최고점을 초과합니다: {', '.join(over)}"
                    )
                st.session_state.score_action_msg = msg
                st.rerun()
```

> 참고: `default_input`의 `max_value`는 저장된 `max_score`로 고정된다. 최고점을 낮추면서 그 아래로 기본점을 내리는 경우는 `default_input > max_input` 검증이 잡는다. 최고점을 올리며 기본점을 옛 상한 위로 한 번에 올리는 드문 경우는 두 번에 나눠 저장한다(수용 가능한 제약).

- [ ] **Step 5: 통과 확인 (GREEN)**

Run: `uv run pytest tests/test_score_page.py -q`
Expected: PASS (전부, 신규 3개 포함).

- [ ] **Step 6: 전체 스위트 확인**

Run: `uv run pytest -q`
Expected: `63 passed`.

- [ ] **Step 7: 커밋**

```bash
git add app/pages/2_점수_관리.py tests/test_score_page.py
git commit -m "$(cat <<'EOF'
feat(scores-page): 기본 점수/최고 점수 편집 '기본 설정' 섹션 추가

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 팀 생성 프롬프트 척도 무관화 (B안)

하드코딩된 `2점 이하와 5점 이상` 문구를 척도 무관 표현으로 바꾼다.

**Files:**
- Modify: `app/utils/build_team_generator_base_prompt_section.py:28`
- Test: `tests/test_team_generator_prompt.py` (신규)

**Interfaces:**
- Consumes: `build_team_generator_prompt` (기존)

- [ ] **Step 1: 실패 테스트 작성 (RED)**

`tests/test_team_generator_prompt.py` 신규:

```python
from app.utils.build_team_generator_base_prompt_section import (
    build_team_generator_prompt,
)


def test_base_prompt_avoids_hardcoded_score_scale():
    prompt = build_team_generator_prompt(
        score_groups={7: ["a"], 1: ["b"]},
        must_link_groups=[],
        cannot_link_groups=[],
        feedback=None,
        team_a=None,
        team_b=None,
    )
    human = prompt[-1].content
    assert "극단 점수대" in human
    assert "2점 이하" not in human
    assert "5점 이상" not in human
```

- [ ] **Step 2: 실패 확인 (RED)**

Run: `uv run pytest tests/test_team_generator_prompt.py -q`
Expected: FAIL — `assert "극단 점수대" in human` 실패(문구 미변경) + `"2점 이하"`가 아직 존재.

- [ ] **Step 3: 프롬프트 문구 교체 (GREEN)**

`app/utils/build_team_generator_base_prompt_section.py:28` 를 교체:

```python
- 특정 점수대 편중 방지(특히 최고점·최저점에 가까운 극단 점수대 편중 방지)
```

- [ ] **Step 4: 통과 확인 (GREEN)**

Run: `uv run pytest tests/test_team_generator_prompt.py -q`
Expected: `1 passed`.

- [ ] **Step 5: 전체 스위트 확인**

Run: `uv run pytest -q`
Expected: `64 passed`.

- [ ] **Step 6: 커밋**

```bash
git add app/utils/build_team_generator_base_prompt_section.py tests/test_team_generator_prompt.py
git commit -m "$(cat <<'EOF'
feat(prompt): 편중 방지 문구를 척도 무관 '극단 점수대'로 일반화

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

**Spec coverage:**
- 저장 구조 `{scores, settings}` → Task 1a(전체 payload) + 1b(settings). ✓
- GitHub 형제 키 보존 → Task 1a 리팩터 + `test_save_scores_github_preserves_settings`. ✓
- 폴백 상수 3/7 → Task 1b. ✓
- `main.py` 주입, 그래프 불변 → Task 2. ✓
- 캡션 `(1~{max_score})` → Task 3a. ✓
- `max_value=7` 두 곳 → `max_score` → Task 3a. ✓
- 추가 프리필 `value=default_score` → Task 3a. ✓
- "기본 설정" expander + `default>max` 검증 + 초과자 경고 → Task 3b. ✓
- 프롬프트 B안 → Task 4. ✓
- 범위 밖(min_value 설정화, 초과 점수 자동 하향, score_fetch_node 합침) → 어느 task도 손대지 않음. ✓

**Placeholder scan:** TODO/TBD 없음. 모든 코드 스텝에 실제 코드 포함. ✓

**Type consistency:** `load_settings()` 반환 `{"default_score", "max_score"}`가 Task 2(`["default_score"]`)·3a(양쪽 키)·3b(입력 초기값)에서 일관. 내부 헬퍼 반환형(파일 전체 `dict`)이 1a→1b→공개 함수에서 일관. ✓
