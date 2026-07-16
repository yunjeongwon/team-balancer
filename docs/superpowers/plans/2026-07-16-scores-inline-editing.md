# 점수 관리 페이지 인라인 편집 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 점수 관리 페이지의 조회/추가/수정/삭제를 정렬 가능한 단일 편집 표 + 접이식 추가 폼으로 통합하고, 저장을 배치로 바꾼다.

**Architecture:** 델타 계산(현재 점수 vs 편집된 표 행 → 추가/수정/삭제)을 순수 함수 `compute_score_delta`로 분리하고, 페이지는 `st.data_editor(num_rows="fixed", disabled=["이름"])`로 정렬을 유지하면서 삭제를 체크박스 컬럼으로 직접 구현한다. 기존 `save_scores`(read-modify-write + sha 재사용)는 그대로 재사용한다.

**Tech Stack:** Streamlit 1.57.0 (`st.data_editor`, `column_config`, `st.form`), pandas, pytest + `streamlit.testing.v1.AppTest`.

**Spec:** `docs/superpowers/specs/2026-07-16-scores-inline-editing-design.md`

## Global Constraints

- Python `>=3.11`, Streamlit `>=1.57.0` (이미 `pyproject.toml`에 있음 — 새 의존성 추가 금지).
- `app/utils/load_scores.py`의 `save_scores`/sha/read-modify-write 로직은 **변경 금지**. 시그니처 `save_scores(updates: dict[str,int] | None = None, deletes: set[str] | None = None)`를 그대로 호출.
- 점수 범위는 정수 1~7. 점수 컬럼 표시 포맷은 `format="%d"`.
- `use_container_width`는 1.57.0에서 폐기됨 — 사용 금지 (`st.data_editor` 기본값 `width="stretch"`에 의존).
- **이름 변경(rename) 미지원.** 이름 컬럼은 `disabled=["이름"]`로 잠근다.
- 컬럼명은 한글 `"이름"`, `"점수"`, `"삭제"` (기존 페이지 관례와 일치).
- 테스트는 `.venv/bin/python -m pytest`로 실행. autouse 픽스처 `isolate_github_token`(conftest.py)이 `GITHUB_TOKEN`을 env에서 제거하므로 `load_scores`/`save_scores`는 로컬 분기(`_scores_path()`)를 탄다.

---

## File Structure

- **Create** `app/utils/compute_score_delta.py` — 순수 델타 계산 함수 하나. 파일당 함수 하나 관례(`compute_team_score_sum.py`)를 따른다.
- **Create** `tests/test_compute_score_delta.py` — 위 함수의 단위 테스트 (실질 커버리지의 본체).
- **Rewrite** `app/pages/2_점수_관리.py` — 3폼 → 단일 편집 표 + 접이식 추가 폼 + 배치 저장.
- **Create** `tests/test_score_page.py` — `AppTest`로 닿는 범위(추가 폼 검증, 추가→저장, 되돌리기, 저장 버튼 비활성).
- **Unchanged** `app/utils/load_scores.py`, `app/main.py`, 그래프 노드, `data/scores.json`, `tests/test_save_scores.py`.

---

## Task 1: 델타 계산 순수 함수

**Files:**
- Create: `app/utils/compute_score_delta.py`
- Test: `tests/test_compute_score_delta.py`

**Interfaces:**
- Consumes: 없음 (표준 라이브러리만).
- Produces: `compute_score_delta(current: dict[str, int], rows: list[dict]) -> tuple[dict[str, int], dict[str, int], set[str]]` — 반환은 `(adds, edits, deletes)`. `rows`의 각 원소는 `{"이름": str, "점수": int(또는 numpy int), "삭제": bool}` 키를 가진다. `adds`=현재에 없는 유지 행, `edits`=현재에 있고 점수가 바뀐 유지 행, `deletes`=`current`엔 있으나 유지 행에 없는 이름.

- [ ] **Step 1: Write the failing tests**

`tests/test_compute_score_delta.py`:

```python
from app.utils.compute_score_delta import compute_score_delta


def _row(name, score, deleted=False):
    return {"이름": name, "점수": score, "삭제": deleted}


def test_no_changes_returns_all_empty():
    current = {"김": 5, "이": 3}
    rows = [_row("김", 5), _row("이", 3)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {}
    assert edits == {}
    assert deletes == set()


def test_score_edit_only():
    current = {"김": 5, "이": 3}
    rows = [_row("김", 7), _row("이", 3)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {}
    assert edits == {"김": 7}
    assert deletes == set()


def test_add_only():
    current = {"김": 5}
    rows = [_row("김", 5), _row("신규", 4)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {"신규": 4}
    assert edits == {}
    assert deletes == set()


def test_delete_only():
    current = {"김": 5, "이": 3}
    rows = [_row("김", 5), _row("이", 3, deleted=True)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {}
    assert edits == {}
    assert deletes == {"이"}


def test_combined_add_edit_delete():
    current = {"김": 5, "이": 3, "박": 1}
    rows = [_row("김", 6), _row("이", 3, deleted=True), _row("박", 1), _row("신규", 2)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {"신규": 2}
    assert edits == {"김": 6}
    assert deletes == {"이"}


def test_pending_add_marked_deleted_is_noop():
    # 추가 대기 행을 삭제 체크하면 순증감 0: adds/edits/deletes 모두 비어야 한다.
    current = {"김": 5}
    rows = [_row("김", 5), _row("신규", 4, deleted=True)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {}
    assert edits == {}
    assert deletes == set()


def test_score_coerced_to_int():
    # data_editor 는 numpy int 를 줄 수 있으므로 int 로 강제되는지 확인.
    current = {"김": 5}
    rows = [_row("김", 7.0)]  # float 입력도 int 로
    _adds, edits, _deletes = compute_score_delta(current, rows)
    assert edits == {"김": 7}
    assert isinstance(edits["김"], int)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_compute_score_delta.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.utils.compute_score_delta'`

- [ ] **Step 3: Write minimal implementation**

`app/utils/compute_score_delta.py`:

```python
def compute_score_delta(
    current: dict[str, int],
    rows: list[dict],
) -> tuple[dict[str, int], dict[str, int], set[str]]:
    """편집된 표 행과 현재 점수를 비교해 (추가, 수정, 삭제) 를 계산한다.

    rows 의 각 원소는 {"이름", "점수", "삭제"} 키를 가진다. 삭제 체크된 행은
    유지 집합(kept)에서 빠지므로, 기존 선수면 deletes 로, 추가 대기 행이면
    아무 델타도 만들지 않는다(순증감 0).
    """
    kept = {r["이름"]: int(r["점수"]) for r in rows if not r["삭제"]}
    adds = {name: score for name, score in kept.items() if name not in current}
    edits = {
        name: score
        for name, score in kept.items()
        if name in current and current[name] != score
    }
    deletes = set(current) - set(kept)
    return adds, edits, deletes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_compute_score_delta.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add app/utils/compute_score_delta.py tests/test_compute_score_delta.py
git commit -m "feat(scores): 점수 편집 델타 계산 순수 함수 추가"
```

---

## Task 2: 페이지 재작성 (단일 편집 표 + 접이식 추가 폼 + 배치 저장)

**Files:**
- Rewrite: `app/pages/2_점수_관리.py`
- Test: `tests/test_score_page.py`

**Interfaces:**
- Consumes: `compute_score_delta` (Task 1); `load_scores()`, `save_scores(updates=, deletes=)` (`app/utils/load_scores.py`, 변경 없음); `require_auth()` (`app/auth.py`).
- Produces: Streamlit 페이지 (반환 인터페이스 없음). `session_state.pending_adds: list[dict]`(`{"이름": str, "점수": int}`)와 위젯 key `"score_editor"`를 사용.

**구현 노트 (실행 전 반드시 읽을 것):**
- 표는 `edited = st.data_editor(...)`의 **반환값**으로 읽는다 (`session_state["score_editor"]`는 델타만 담으므로 사용하지 않는다). `rows = edited.to_dict("records")`.
- 저장 성공 후 `st.session_state.pop("score_editor", None)` + `st.session_state.pending_adds = []`로 위젯 상태를 비운다. 안 그러면 `data_editor`가 행 위치로 캐시한 낡은 편집이 다음 렌더에서 엉뚱한 행에 재적용된다.
- 추가 폼 제출은 즉시 저장하지 않고 `pending_adds`에 append 후 `st.rerun()`. 대기 행은 표 **끝**에 붙인다.
- 저장 **실패** 시 `st.error`만 띄우고 `st.rerun()`을 호출하지 않는다 (편집 보존).
- AppTest는 `data_editor` 셀 편집/삭제 체크를 구동할 수 없다(확인됨). 따라서 테스트는 추가 폼·저장 경로·되돌리기·버튼 비활성만 덮고, 셀 편집/삭제 UI는 수동 확인에 의존한다.

- [ ] **Step 1: Write the failing page tests**

`tests/test_score_page.py`:

```python
import json

from streamlit.testing.v1 import AppTest

from app.utils import load_scores as ls

PAGE = "app/pages/2_점수_관리.py"


def _seed(tmp_path, monkeypatch, scores):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(
        json.dumps({"scores": scores}, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)
    return fake_path


def _run(tmp_path, monkeypatch, scores):
    _seed(tmp_path, monkeypatch, scores)
    at = AppTest.from_file(PAGE)
    at.session_state["authenticated"] = True
    at.run()
    return at


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def test_add_form_rejects_empty_name(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, {"김동영": 7})
    _button(at, "추가").click().run()
    assert any("이름을 입력해주세요" in e.value for e in at.error)


def test_add_form_rejects_existing_name(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, {"김동영": 7})
    at.text_input[0].set_value("김동영").run()
    _button(at, "추가").click().run()
    assert any("이미 등록된 선수" in e.value for e in at.error)


def test_add_form_rejects_duplicate_pending(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, {"김동영": 7})
    at.text_input[0].set_value("신규").run()
    _button(at, "추가").click().run()
    at.text_input[0].set_value("신규").run()
    _button(at, "추가").click().run()
    assert any("이미 추가 대기 중" in e.value for e in at.error)


def test_add_then_save_persists(tmp_path, monkeypatch):
    fake_path = _seed(tmp_path, monkeypatch, {"김동영": 7})
    at = AppTest.from_file(PAGE)
    at.session_state["authenticated"] = True
    at.run()

    at.text_input[0].set_value("신규").run()  # 점수는 기본값 4
    _button(at, "추가").click().run()
    _button(at, "저장").click().run()

    saved = json.loads(fake_path.read_text(encoding="utf-8"))["scores"]
    assert saved == {"김동영": 7, "신규": 4}


def test_revert_clears_pending(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, {"김동영": 7})
    at.text_input[0].set_value("신규").run()
    _button(at, "추가").click().run()
    assert at.session_state["pending_adds"] == [{"이름": "신규", "점수": 4}]

    _button(at, "되돌리기").click().run()
    assert at.session_state["pending_adds"] == []


def test_save_button_disabled_when_no_changes(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, {"김동영": 7})
    assert _button(at, "저장").disabled is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_score_page.py -v`
Expected: FAIL — 현재 페이지엔 "추가"/"되돌리기" 버튼도 `pending_adds`도 없어 `StopIteration`/`KeyError`로 실패.

- [ ] **Step 3: Rewrite the page**

`app/pages/2_점수_관리.py` (전체 교체):

```python
import sys
from pathlib import Path

# Streamlit Cloud는 레포 루트를 sys.path에 넣지 않으므로 app.* 임포트 전에 직접 추가한다.
# 페이지 스크립트는 main.py를 거치지 않고 독립 실행될 수 있어 여기에도 필요하다.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import streamlit as st

from app.auth import require_auth
from app.utils.compute_score_delta import compute_score_delta
from app.utils.load_scores import load_scores, save_scores

require_auth()

st.title("점수 관리")
st.caption(
    "선수 이름과 실력 점수(1~7)를 관리합니다. 점수 셀을 눌러 수정하고, 삭제할 선수는 "
    "삭제 열을 체크한 뒤 저장하세요. 표 헤더(이름/점수)를 클릭하면 정렬됩니다."
)

# 직전 저장 결과 메시지. st.rerun() 직전의 st.success/toast 는 rerun 에 의해
# 무시되므로 session_state 로 넘겨 여기서 표시한다.
if "score_action_msg" in st.session_state:
    st.toast(st.session_state.score_action_msg, icon="✅")
    del st.session_state.score_action_msg

if "pending_adds" not in st.session_state:
    st.session_state.pending_adds = []


def _current_scores() -> dict[str, int]:
    try:
        return load_scores()
    except Exception as e:  # 파일 손상/부재
        st.error(f"scores.json 을 불러오지 못했습니다: {e}")
        st.stop()


scores = _current_scores()

# --- 추가: 접이식 폼 (배치에 참여, 즉시 저장 안 함) ---
with st.expander("선수 추가"):
    with st.form("add_form", clear_on_submit=True):
        new_name = st.text_input("이름")
        new_score = st.number_input("점수", min_value=1, max_value=7, value=4, step=1)
        add_submitted = st.form_submit_button("추가")

    if add_submitted:
        name = new_name.strip()
        pending_names = {a["이름"] for a in st.session_state.pending_adds}
        if not name:
            st.error("이름을 입력해주세요.")
        elif name in scores:
            st.error("이미 등록된 선수입니다. 표에서 점수를 수정하세요.")
        elif name in pending_names:
            st.error("이미 추가 대기 중인 이름입니다.")
        else:
            st.session_state.pending_adds.append(
                {"이름": name, "점수": int(new_score)}
            )
            st.rerun()

# --- 편집 표: 기존 선수(이름순) + 추가 대기 행(끝에 append) ---
table_rows = [
    {"이름": name, "점수": score, "삭제": False}
    for name, score in sorted(scores.items())
]
table_rows += [
    {"이름": a["이름"], "점수": a["점수"], "삭제": False}
    for a in st.session_state.pending_adds
]
df = pd.DataFrame(table_rows, columns=["이름", "점수", "삭제"])

edited = st.data_editor(
    df,
    key="score_editor",
    num_rows="fixed",  # 정렬 유지 (dynamic/add 는 정렬 비활성)
    hide_index=True,
    disabled=["이름"],  # 이름 잠금: 오타로 새 선수가 생기는 사고 방지
    column_config={
        "이름": st.column_config.TextColumn("이름"),
        "점수": st.column_config.NumberColumn(
            "점수", min_value=1, max_value=7, step=1, format="%d"
        ),
        "삭제": st.column_config.CheckboxColumn("삭제"),
    },
    column_order=["이름", "점수", "삭제"],
)

adds, edits, deletes = compute_score_delta(scores, edited.to_dict("records"))
has_changes = bool(adds or edits or deletes)

st.caption(f"추가 {len(adds)} · 수정 {len(edits)} · 삭제 {len(deletes)}")

save_col, revert_col = st.columns(2)
save_clicked = save_col.button(
    "저장", type="primary", disabled=not has_changes
)
revert_clicked = revert_col.button("되돌리기")

if revert_clicked:
    st.session_state.pop("score_editor", None)
    st.session_state.pending_adds = []
    st.rerun()

if save_clicked:
    try:
        with st.spinner("저장 중..."):
            save_scores(updates={**adds, **edits}, deletes=deletes)
    except Exception as e:
        # 실패 시 rerun 하지 않아 표의 편집을 보존한다.
        st.error(f"저장 중 오류가 발생했습니다: {e}")
    else:
        st.session_state.pop("score_editor", None)
        st.session_state.pending_adds = []
        st.session_state.score_action_msg = (
            f"저장되었습니다. (추가 {len(adds)} · 수정 {len(edits)} · 삭제 {len(deletes)})"
        )
        st.rerun()
```

- [ ] **Step 4: Run the page tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_score_page.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 기존 `test_save_scores.py`, `test_main_app.py`, `test_streamlit_cloud_imports.py` 포함 전부 통과.

- [ ] **Step 6: Commit**

```bash
git add app/pages/2_점수_관리.py tests/test_score_page.py
git commit -m "feat(scores): 점수 관리 페이지를 인라인 편집 표 + 배치 저장으로 재작성"
```

---

## Task 3: 수동 검증 (앱 구동)

**Files:** 없음 (실행 확인만).

- [ ] **Step 1: 앱 실행**

Run: `.venv/bin/python -m streamlit run app/main.py`
로그인 후 사이드바 "점수 관리" 이동.

- [ ] **Step 2: 다음을 눈으로 확인**

1. 표에서 **점수 헤더 클릭 → 정렬**이 동작한다 (fixed 모드 유지 확인).
2. 점수 셀을 고치면 하단 요약이 "수정 1"로 바뀌고 [저장]이 활성화된다.
3. 삭제 열 체크 → "삭제 N", 언체크 → 원복.
4. "선수 추가" 펼쳐 이름+점수 입력 후 [추가] → 표 끝에 대기 행이 붙고 "추가 1".
5. [저장] → 스피너 후 toast, 표가 갱신되고 요약이 "추가 0 · 수정 0 · 삭제 0".
6. 변경 없을 때 [저장]은 비활성.
7. 편집/추가 후 [되돌리기] → 미저장 변경이 모두 사라짐.

- [ ] **Step 3: 커밋 불필요 (코드 변경 없음)**

---

## Self-Review (작성자 확인 완료)

- **Spec coverage:** 이름 잠금(Task 2 `disabled=["이름"]`), fixed+체크박스 삭제(Task 2), 배치 저장+변경 요약(Task 2), 대기 행 끝 append(Task 2), 저장 후 위젯 정리(Task 2 Step 3), 저장 실패 시 편집 보존(Task 2), 추가 폼 검증 3종(Task 2 테스트), 델타 순수 함수+테스트(Task 1), AppTest 사각지대 명시(Task 2 노트 + Task 3 수동 검증) — 모두 태스크로 매핑됨.
- **Placeholder scan:** 모든 코드 스텝에 실제 코드 포함, TBD/TODO 없음.
- **Type consistency:** `compute_score_delta(current, rows) -> (adds, edits, deletes)` 시그니처가 Task 1 정의와 Task 2 호출부에서 일치. `save_scores(updates=, deletes=)` 시그니처가 기존 코드와 일치. `pending_adds` 원소 형태 `{"이름": str, "점수": int}`가 페이지·테스트에서 일관.
