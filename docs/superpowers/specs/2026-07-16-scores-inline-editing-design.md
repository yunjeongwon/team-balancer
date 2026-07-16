# 점수 관리 페이지 인라인 편집 설계

**날짜:** 2026-07-16
**목표:** `app/pages/2_점수_관리.py`의 조회/추가/수정/삭제를 하나의 편집 가능한 표로 통합하고, 저장을 배치로 바꾼다. 정렬은 유지한다.

## 배경

현재 페이지는 읽기 전용 `st.dataframe`(헤더 클릭 정렬) + 추가/수정 폼 + 삭제 폼의 3개 섹션이며, 각 폼은 즉시 저장한다. 세 가지 문제가 있다.

1. **이름 오타가 조용히 새 선수를 만든다.** 수정하려면 이름을 직접 타이핑해야 하는데, `name in scores` 검사가 곧 추가/수정 분기다. 현재 36명 중 "김동영/김동혁", "김재광/김태일"처럼 비슷한 이름이 있어 오타 시 에러 없이 신규 선수가 생긴다.
2. **저장 중 피드백이 없다.** GitHub 백엔드에서 저장 1건은 GET(sha) + PUT + rerun GET으로 최대 3회 왕복하는데 스피너가 없어 중복 클릭 위험이 있다.
3. **삭제에 확인 단계가 없다.** multiselect에서 고르고 누르면 즉시 커밋된다.

### 선행 시도와 교착

`docs/superpowers/specs/2026-07-12-scores-crud-design.md`는 이미 `st.data_editor(num_rows="dynamic")`를 결정했으나, 구현 커밋 `73216f4`는 이를 따르지 않고 3폼 설계로 갔다. 커밋 메시지가 "**Sortable** read-only table (st.dataframe, click headers) + add/edit form + delete form"이라고 정렬을 명시한다.

이유는 Streamlit의 제약으로 보인다 (1.57.0 `st.data_editor` docstring 확인):

| `num_rows` | 동작 | 정렬 |
|---|---|---|
| `"fixed"` (기본) | 추가·삭제 불가 | 유지 |
| `"dynamic"` | 추가+삭제 | **비활성** |
| `"add"` | 추가만 | **비활성** |
| `"delete"` | 삭제만 | 유지 |

즉 스펙이 원한 인라인 편집(`dynamic`)과 구현이 지킨 정렬은 양립 불가였고, 구현은 정렬을 택해 폼으로 우회했다.

**이 설계는 그 교착을 푼다.** `num_rows="fixed"`로 정렬을 지키면서, 행 추가/삭제만 위젯 바깥에서 직접 구현한다 — 삭제는 체크박스 컬럼, 추가는 별도 폼. 둘 다 얻는다.

## 범위 (In scope)

- 페이지 UI 재구성: 편집 가능한 단일 표 + 접이식 추가 폼
- 배치 저장 (변경 요약 → 저장 1회) 및 되돌리기
- 델타 계산 순수 함수 추출 및 단위 테스트
- 저장 중 스피너, 저장 실패 시 편집 보존

## 범위 외 (Out of scope)

- `app/utils/load_scores.py`의 `save_scores`/sha 재사용/read-modify-write 로직 — 변경 없음
- `app/main.py`, 그래프 노드, `data/scores.json` 구조 — 변경 없음
- **이름 변경(rename)** — 지원하지 않는다. 삭제 후 재추가로 대체한다.
- `load_scores()` 캐싱 (`st.cache_data`) — 별개 관심사
- GitHub 409 등 개별 실패 케이스의 전용 메시지 — 단일 편집자 가정이 `load_scores.py`에 이미 문서화됨. 포괄 핸들러에 맡긴다.
- 검색/필터 — 36명 규모에서 불필요. 표를 필터링하면 델타 계산의 기준 집합이 어긋나 위험하기도 하다.

## 결정된 접근법

1. **`num_rows="fixed"` + 삭제 체크박스 컬럼.** 정렬 유지가 이유다. `num_rows="delete"`도 정렬을 유지하지만 채택하지 않는다 — 내장 삭제는 행이 즉시 사라져 저장 전인데 이미 지워진 듯한 착각을 주고, 개별 취소가 불가능해 되돌리려면 전체를 버려야 한다. 배치 저장에는 "☑ 삭제 예정"이 저장 시점까지 보이고 언체크로 개별 취소되는 쪽이 맞다.
2. **이름 컬럼 잠금 (`disabled=["이름"]`).** 배경 1번 문제를 구조적으로 제거한다 — 기존 선수의 이름은 타이핑할 일이 없어진다. 대가는 rename 불가이며, 사용자가 삭제 후 재추가로 충분하다고 확인했다.
3. **추가도 배치에 참여.** "추가"는 즉시 저장하지 않고 대기 행으로 표 끝에 붙는다. 저장 모델이 한 페이지에 둘이면 혼란스럽고, 즉시 저장은 rerun을 일으켜 표의 미저장 편집을 깨뜨린다.
4. **대기 행은 표 끝에 append.** `data_editor`는 편집 델타를 행 위치로 캐시하므로, 이름순 중간에 삽입하면 뒤 행들의 편집이 밀려 엉뚱한 행에 얹힌다. 끝에 붙이면 기존 위치가 불변이다. 이름 헤더 클릭으로 정렬해 보면 되므로 실사용 지장은 없다.

## 화면

```
점수 관리
선수 이름과 실력 점수(1~7)를 관리합니다.

▸ 선수 추가                          ← expander, 기본 접힘
    이름 [________]  점수 [4]  [추가]     (st.form, 엔터 제출)

  이름 ↕      점수 ↕     삭제
  김동영        7        ☐
  김상래        6        ☐        ← 점수 셀만 편집 가능
  박종민        1        ☑
  신규선수       4        ☐        ← 대기 행 (끝에 append)
  ─────────────────────────
  추가 1 · 수정 1 · 삭제 1
  [ 저장 ]  [ 되돌리기 ]
```

변경이 없으면 [저장]은 비활성. [되돌리기]는 미저장 편집과 대기 행을 모두 버린다.

표는 `st.form` 안에 두지 않는다 — 폼 안에서는 위젯이 실시간 갱신되지 않아 변경 요약을 즉시 보여줄 수 없다. 추가 폼만 `st.form`을 유지한다 (엔터 제출, 커밋 `66746d1`의 의도).

## 컴포넌트

### A. 델타 계산 — `app/utils/compute_score_delta.py` (신규)

레포 관례(`compute_team_score_sum.py` 등, 파일당 함수 하나 + 짝맞는 테스트)를 따른다.

```python
def compute_score_delta(
    current: dict[str, int],
    rows: list[dict],
) -> tuple[dict[str, int], dict[str, int], set[str]]:
    """편집된 표 행과 현재 점수를 비교해 (추가, 수정, 삭제) 를 계산한다."""
    kept = {r["이름"]: int(r["점수"]) for r in rows if not r["삭제"]}
    adds = {n: s for n, s in kept.items() if n not in current}
    edits = {n: s for n, s in kept.items() if n in current and current[n] != s}
    deletes = set(current) - set(kept)
    return adds, edits, deletes
```

표는 항상 `current`의 모든 선수를 보여주므로 `set(current) - set(kept)`는 삭제 체크된 행과 정확히 일치한다.

### B. 페이지 — `app/pages/2_점수_관리.py` (재작성)

`session_state.pending_adds`: `[{"이름": str, "점수": int}, ...]`

흐름:
1. `scores = load_scores()`
2. df 구성: `scores`(이름순) + `pending_adds`(끝에 append), `삭제` 컬럼은 전부 `False`
3. `st.data_editor(df, key="score_editor", num_rows="fixed", disabled=["이름"], hide_index=True, column_config=...)`
4. 반환된 df → `compute_score_delta(scores, rows)`
5. 변경 요약 렌더 + [저장]`disabled=not (adds or edits or deletes)` / [되돌리기]
6. 저장: `with st.spinner("저장 중..."):` → `save_scores(updates={**adds, **edits}, deletes=deletes)`

`column_config`:
- `이름`: `TextColumn` (컬럼 자체는 `disabled`)
- `점수`: `NumberColumn(min_value=1, max_value=7, step=1, format="%d")`
- `삭제`: `CheckboxColumn`

`use_container_width`는 1.57.0에서 폐기됐다. 기본값이 `width="stretch"`이므로 생략한다.

### C. 저장 후 정리 — 중요

```python
st.session_state.pop("score_editor", None)
st.session_state.pending_adds = []
st.session_state.score_action_msg = "..."
st.rerun()
```

`score_editor` 위젯 상태를 반드시 비운다. `data_editor`는 편집 델타를 행 위치로 캐시하므로, 저장으로 행이 사라지면 위치가 밀려 낡은 편집이 엉뚱한 행에 재적용된다.

`score_action_msg` → toast 패턴은 기존 코드(커밋 `9b09c8b`)를 그대로 유지한다.

## 데이터 흐름

```
load_scores()  ->  dict[str, int]
  + session_state.pending_adds
  -> DataFrame[이름, 점수, 삭제]
  -> st.data_editor (fixed, 이름 잠금, 정렬 가능)
  -> compute_score_delta(scores, rows) -> (adds, edits, deletes)   # 순수 함수
  -> 변경 요약 렌더
  -> [저장] -> save_scores(updates={**adds, **edits}, deletes=deletes)
             -> (기존) 최신 재읽기 + sha 재사용 PUT
  -> session_state 정리 -> st.rerun() -> toast
```

## 검증 규칙

이름 컬럼이 잠겨 있으므로 **표에서는 빈 이름도 중복도 새로 생길 수 없다.** 점수는 `NumberColumn(min_value=1, max_value=7)`이 위젯 차원에서 막는다. 따라서 검증은 추가 폼에만 필요하다.

추가 폼 (`name.strip()` 후):
- 빈 이름 → "이름을 입력해주세요."
- 이미 `scores`에 존재 → "이미 등록된 선수입니다. 표에서 점수를 수정하세요."
- 이미 `pending_adds`에 존재 → "이미 추가 대기 중인 이름입니다."

## 에러 처리

- `load_scores()` 실패: 기존과 동일 (`st.error` + `st.stop()`)
- `save_scores()` 실패: `st.error`만 띄우고 **`st.rerun()`을 하지 않는다.** 표의 편집이 살아있어 재시도할 수 있다. 실패했는데 편집이 날아가는 것이 최악의 결과다.

## 테스트 계획

**제약:** `AppTest`는 `data_editor`를 지원하지 않는다 (1.57.0에서 확인 — `dataframe`, `table`만 있음). **점수 셀 편집과 삭제 체크는 AppTest로 구동할 수 없다.** 따라서 실질 커버리지를 순수 함수에 둔다.

`tests/test_compute_score_delta.py` — 로직의 본체:
- 변경 없음 → 셋 다 빈 값
- 점수 수정만
- 추가만 (대기 행)
- 삭제만 (삭제 체크)
- 복합 (추가+수정+삭제 동시)
- 대기 행을 삭제 체크 → 순증감 0 (추가되지 않음)

`tests/test_score_page.py` — `AppTest`로 닿는 범위:
- 추가 폼 검증 에러 3종 (`at.error`)
- 추가 → 저장 경로: `save_scores`를 monkeypatch해 `updates` 인자 검증 (추가는 `session_state`를 타므로 구동 가능)
- 되돌리기 → `pending_adds` 비워짐
- 변경 없을 때 저장 버튼 비활성

기존 `tests/test_save_scores.py`, `tests/test_streamlit_cloud_imports.py`는 변경 없이 통과해야 한다.

**사각지대:** 셀 편집·삭제 체크의 UI 상호작용 자체는 자동 테스트로 덮이지 않으며 수동 확인에 의존한다.

## 영향 분석

- `app/utils/compute_score_delta.py`: 신규
- `app/pages/2_점수_관리.py`: 재작성
- `tests/test_compute_score_delta.py`, `tests/test_score_page.py`: 신규
- `app/utils/load_scores.py`, `app/main.py`, 그래프 노드, `data/scores.json`: 변경 없음
- `docs/superpowers/specs/2026-07-12-scores-crud-design.md`: 이 문서가 대체 (삭제하지 않음)
