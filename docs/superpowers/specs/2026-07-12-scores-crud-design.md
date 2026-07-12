# scores.json CRUD 페이지 설계

**날짜:** 2026-07-12
**목표:** `data/scores.json`의 선수 점수 데이터를 Streamlit UI에서 생성(Create)/조회(Read)/수정(Update)/삭제(Delete) 할 수 있는 페이지를 추가한다.

## 배경

`data/scores.json`은 `{"scores": {"<이름>": <1~7 정수>}}` 구조로, 팀 밸런싱 시 각 선수의 실력 가중치로 사용된다. 현재는 파일을 직접 편집해야 하므로, 실수로 JSON 구조를 망가뜨릴 위험이 있고 불편하다.

현재 읽기 흐름:
- `app/utils/load_scores.py::load_scores()`가 매 호출마다 디스크에서 새로 읽는다 (캐시 없음).
- `app/graph/nodes/score_fetch_node.py`가 이를 호출해 `member_scores`를 채운다.

이 흐름은 캐시가 없으므로, CRUD로 파일을 갱신하면 다음 "팀 생성" 실행 시 자동 반영된다 (캐시 무효화 불필요).

## 범위 (In scope)

- 점수 조회/추가/수정/삭제 UI 페이지
- 디스크 영속화 (원자적 쓰기)
- 입력 검증 (이름 중복, 점수 범위 1~7)
- 영속성 로직에 대한 단위 테스트

## 범위 외 (Out of scope)

- 메인 팀 밸런서 페이지(`app/main.py`) 변경 없음
- 점수 범위(1~7) 자체의 변경, 점수 이력/감사 로그
- 인증/권한, 다중 사용자 동시 편집 충돌 처리

## 결정된 접근법

1. **페이지 통합:** Streamlit 레거시 `pages/` 폴더 방식. `app/pages/2_점수_관리.py` 추가. `app/main.py`는 변경하지 않는다 (가장 surgical).
2. **CRUD UX:** `st.data_editor` 인라인 표. 모든 선수를 편집 가능한 표로 표시, "저장" 버튼 클릭 시에만 디스크 반영.

## 컴포넌트

### A. 영속성 계층 — `app/utils/load_scores.py` (기존 파일 확장)

기존 `load_scores()`는 그대로 유지하고(다른 import에 영향 주지 않음), 두 함수를 추가한다.

```python
def save_scores(scores: dict[str, int]) -> None:
    """{"scores": {...}} 래퍼 구조를 보존하여 scores.json에 원자적으로 기록.
    임시 파일(scores.json.tmp)에 쓴 뒤 os.replace()로 교체한다."""

def validate_scores(names: list[str], scores_list: list[int]) -> list[str]:
    """data_editor 편집 결과를 검증. 빈 이름 행은 무시(자동 skip).
    반환값: 에러 메시지 리스트. 빈 리스트면 유효.
    - 이름 중복(공백 trim 후) 감지
    - 점수가 정수 1~7 범위 밖이면 감지"""
```

경로 계산은 기존 `load_scores()`의 방식(`team-balancer` 루트 탐색)을 `save_scores`도 동일하게 사용한다. (리팩터링 최소화를 위해 허용되는 중복)

### B. 페이지 — `app/pages/2_점수_관리.py` (신규)

Streamlit은 메인 스크립트(`app/main.py`)와 같은 디렉터리의 `pages/` 폴더를 자동 인식해 사이드바에 페이지 항목을 추가한다. 파일명 `2_점수_관리.py`는 사이드바에 "점수 관리"로 표시된다 (앞 숫자는 정렬용).

페이지 흐름:
1. `st.title("점수 관리")`
2. `load_scores()` → `pandas.DataFrame[이름, 점수]` 변환
3. `st.data_editor(df, num_rows="dynamic", column_config={"점수": NumberColumn(min_value=1, max_value=7, step=1)})`로 인라인 편집 표 표시
4. **저장 버튼:** 편집된 DataFrame에서 `validate_scores()` 호출
   - 에러 있으면 `st.error(" ".join(errors))`, 저장 중단
   - 에러 없으면 `save_scores(dict)`, `st.success("저장되었습니다.")`
5. **새로고침 버튼:** 디스크에서 다시 불러와 편집 중 변경분 취소

## 데이터 흐름

```
scores.json
  --load_scores()--> dict
  --> DataFrame[이름, 점수]
  --> st.data_editor (인라인 편집, 행 추가/삭제, num_rows="dynamic")
  --> [저장 클릭]
  --> validate_scores(names, scores) -> list[str]  (순수 함수)
  --> [] 이면 save_scores(dict) -> 원자적 쓰기 (tmp + os.replace)
  --> scores.json
  --> 다음 "팀 생성" 실행 시 score_fetch_node 가 자동 반영
```

## 검증 규칙

- **이름:** 값의 앞뒤 공백 제거(strip). 빈 문자열이면 해당 행을 무시(추가되지 않음). 중복 이름(2개 이상 행이 같은 strip 후 이름)이면 저장 거부하고 어떤 이름이 충돌했는지 메시지에 표시.
- **점수:** 정수 1~7 이외 값이면 저장 거부. `NumberColumn(min=1, max=7)`이 UI에서 1차 방어하지만, 저장 시에도 `validate_scores`가 2차 방어한다.

## 에러 처리

- 파일 읽기 실패(파일 없음/JSON 손상): 페이지에서 `try/except`, `st.error`로 표시.
- 파일 쓰기 실패(권한 등): `save_scores`에서 예외 발생, 페이지에서 catch하여 `st.error` 표시. 임시 파일은 제거.
- 검증 실패: 저장하지 않고 `st.error`로 상세 표시.

## 테스트 계획 (TDD)

`validate_scores`와 `save_scores`는 순수/부수효과 함수로 분리해 단위 테스트한다. Streamlit 렌더링 자체는 기존 그래프 노드와 동일하게 단위 테스트 범위에서 제외한다.

`tests/test_save_scores.py`:
- round-trip: `load_scores()` 원본 → `save_scores()` → 다시 `load_scores()` == 원본
- 원자적 쓰기: 저장 성공 후 `scores.json.tmp`가 남아있지 않음
- 래퍼 구조 보존: 저장된 파일이 `{"scores": {...}}` 형태

`tests/test_validate_scores.py`:
- 정상 케이스: 빈 리스트 반환
- 중복 이름 감지: 해당 이름이 에러 메시지에 포함
- 점수 범위 위반(0, 8, -1) 감지
- 빈 이름 행은 무시(에러 아님)

## 영향 분석

- `app/utils/load_scores.py`: 함수 2개 추가 (기존 `load_scores` 변경 없음)
- `app/pages/2_점수_관리.py`: 신규 파일
- `data/scores.json`: 구조 변경 없음 (`{"scores": {...}}` 유지)
- `app/main.py`, 그래프 노드, 기존 테스트: 변경 없음
- `score_fetch_node`: `load_scores()` 그대로 사용하므로 CRUD 결과를 자동 반영

## 파일 위치 비고

- `app/pages/` (프로젝트 루트 `pages/`가 아님). Streamlit의 `pages/` 폴더는 메인 스크립트(`app/main.py`)와 같은 디렉터리에 있어야 자동 인식된다.
