# 기본 점수 / 최고 점수 설정화 설계

작성일: 2026-07-17

## 배경

`app/main.py`가 그래프를 호출할 때 `default_score`(점수 미등록 인원에게 매길 점수)를
`4`로 하드코딩하고 있다([main.py:152](../../../app/main.py#L152)). 이 값을 3으로 바꾸고
싶다는 요구에서 출발했으나, 앞으로 가끔 조정될 값으로 판단되어 점수 관리 페이지에서
편집 가능하게 만든다. 최고 점수(현재 `7`)도 가끔 바뀔 수 있어 함께 설정화한다.

두 값은 **배포 설정이 아니라 도메인 데이터**다. "미등록자를 몇 점으로 볼지", "최고점을
몇 점까지 둘지"는 점수 자체와 같은 성격의 규칙이므로 점수 옆(`scores.json`)에 둔다.
환경변수는 값 하나 바꾸려고 Secrets 편집→리부트가 필요해 오히려 불편하므로 배제한다.

## 성격이 다른 두 값

| 값 | 성격 | 그래프에 들어가나 |
|---|---|---|
| `default_score` | 점수 계산에 실제로 쓰이는 값 | **예** — state로 주입, `score_fetch_node`가 사용 |
| `max_score` | 점수 입력의 검증 상한일 뿐 | **아니오** — 점수 관리 페이지만 참조 |

현재 `7`은 그래프 로직·LLM 프롬프트 어디에도 없고 점수 관리 페이지 세 곳에만 있다:
캡션([2_점수_관리.py:19](../../../app/pages/2_점수_관리.py#L19)), "선수 추가" 폼의
`number_input`([2_점수_관리.py:47](../../../app/pages/2_점수_관리.py#L47)),
`data_editor`의 점수 컬럼([2_점수_관리.py:85](../../../app/pages/2_점수_관리.py#L85)).

## 저장 구조

`data/scores.json`에 `settings` 형제 키를 추가한다:

```json
{
  "scores": { "윤정원": 2, "권진현": 4, "...": 0 },
  "settings": { "default_score": 4, "max_score": 7 }
}
```

### 핵심: GitHub 백엔드의 "형제 키 소실" 함정을 구조적으로 제거

현재 `load_scores.py`는 파일에서 `["scores"]`만 꺼내
([load_scores.py:63](../../../app/utils/load_scores.py#L63)) 저장 시
`{"scores": scores}`로 통째로 덮어쓴다
([load_scores.py:94](../../../app/utils/load_scores.py#L94)). 여기에 `settings`를
얹기만 하면, **배포 환경에서 선수 한 명 추가하는 순간 `settings`가 조용히 사라진다.**

따라서 내부 표현을 **"scores 딕셔너리"에서 "파일 전체 딕셔너리"로** 바꾼다. 읽을 때
payload 전체(`{"scores": ..., "settings": ...}`)를 들고 있다가 쓸 때 전체를 되돌려쓰면,
모르는 키가 있어도 보존된다. `settings`뿐 아니라 향후 어떤 키를 추가해도 같은 버그가
재발하지 않는다.

### 폴백

`data/scores.json`에는 아직 `settings` 키가 없다. 파일을 미리 손대는 대신
`app/constants.py`에 상수를 두고 부재 시 폴백으로 쓴다. 로컬 파일과 `scores-data`
브랜치 파일이 따로 노는 이중 백엔드 구조라, 양쪽을 미리 시딩하는 것보다 폴백이 안전하다.

```python
# app/constants.py (기존 PLACEHOLDER_MEMBER 옆에 추가)
DEFAULT_SCORE = 3
MAX_SCORE = 7
```

`settings` 키 자체가 없거나 일부 하위 키만 있어도 각 값을 상수로 개별 폴백한다.

## `load_scores.py` API 변경

내부 헬퍼를 "파일 전체 dict"를 다루도록 리팩터하고, 공개 함수는 그 위에 얇게 얹는다.
각 공개 함수는 **전체 파일 단위 read-modify-write**를 수행하므로 서로의 키를 침범하지
않는다(scores 저장이 settings를 지우지 않고, settings 저장이 scores를 지우지 않는다).

### 내부 헬퍼 (전체 payload 기준으로 재작성)

- `_load_local() -> dict` — 파일 전체 dict 반환 (기존은 `["scores"]`만 반환했음)
- `_save_local(data: dict)` — 전체 dict를 원자적으로 기록 (기존 tmp+os.replace 방식 유지)
- `_load_github_with_sha() -> tuple[dict, str]` — 전체 dict + sha
- `_load_github() -> dict` — 전체 dict (sha 불필요 경로)
- `_save_github(data: dict, sha)` — 전체 dict 저장
- `_load_full() -> dict` — 토큰 유무로 `_load_github()`/`_load_local()`을 분기하는
  읽기 전용 래퍼. `load_scores()`·`load_settings()`가 이것을 쓴다. 저장 경로는 sha
  동시성 처리가 필요해 이 래퍼를 쓰지 않고 `save_scores`/`save_settings`가 각자
  백엔드를 분기한다(기존 `save_scores`와 동일한 구조).

### 공개 함수

```python
def load_scores() -> dict[str, int]:
    """선수→점수 매핑만 반환 (하위호환 유지)."""
    return _load_full().get("scores", {})

def load_settings() -> dict:
    """{"default_score": int, "max_score": int} — 부재 키는 상수로 폴백."""
    settings = _load_full().get("settings", {})
    return {
        "default_score": settings.get("default_score", DEFAULT_SCORE),
        "max_score": settings.get("max_score", MAX_SCORE),
    }

def save_scores(updates=None, deletes=None) -> None:
    """전체 파일을 (재)읽어 scores에만 델타를 적용하고 전체를 저장."""

def save_settings(default_score: int, max_score: int) -> None:
    """전체 파일을 (재)읽어 settings만 교체하고 전체를 저장."""
```

- `load_scores()`의 시그니처·반환형은 그대로다 → `score_fetch_node`, 점수 관리 페이지의
  조회 표는 변경 불필요.
- `save_scores`/`save_settings` 모두 GitHub 백엔드에서는 읽어온 sha를 PUT에 재사용하는
  기존 동시성 처리(409 감지)를 유지한다.

## 그래프 / main.py

`default_score`는 **state에 그대로 둔다.** `main.py`가 저장소에서 읽어 주입하는 방식:

```python
# app/main.py
from app.utils.load_scores import load_settings
...
app.invoke(
    {
        ...,
        "default_score": load_settings()["default_score"],  # 하드코딩 4 제거
    },
    config=config,
)
```

`state.py`, `score_fetch_node.py`, 그래프 빌더는 **손대지 않는다.** score_fetch_node가
이미 `load_scores()`를 부르고 있어 거기서 함께 읽으면 GitHub GET을 1회 줄일 수 있으나,
그러려면 state·main·테스트 여러 곳을 건드리고 그래프가 저장소에 더 얽힌다. GET 1회
추가 비용은 이 앱 규모에서 무의미하므로(제한 5000/시간), 주입 지점을 main에 두어 그래프를
저장소와 분리된 채로 유지한다. 테스트가 `default_score`를 명시적으로 주입하는 현재 구조도
그대로 살아 있다.

`max_score`는 그래프에 들어가지 않는다.

## 점수 관리 페이지 UI

현재 페이지는 **`st.data_editor` 인라인 편집 버전**이다
([2_점수_관리.py](../../../app/pages/2_점수_관리.py)). 폼 기반이 아니다. 페이지 상단에서
`settings = load_settings()`를 한 번 읽어 아래 세 곳에 쓴다.

### 1. "기본 설정" expander 추가

기존 "선수 추가" expander 옆에 접이식 **"기본 설정"** 섹션을 둔다. 점수 표 저장과 분리된,
`save_settings()`를 부르는 독립 저장 버튼을 갖는다.

```
▸ 기본 설정
    미등록 인원에게 적용할 점수  [ 3 ]   (min_value=1, max_value=max_score)
    최고 점수                    [ 7 ]   (min_value=1, max_value=20 고정)
    [설정 저장]
```

- 초기값은 `settings["default_score"]`, `settings["max_score"]`.

### 2. 캡션 동적화

[2_점수_관리.py:19](../../../app/pages/2_점수_관리.py#L19)의 "(1~7)"만
`f"(1~{max_score})"`로 바꾼다. 나머지 문구("점수 셀을 눌러 수정하고…")는 그대로 둔다.

- Before: `"선수 이름과 실력 점수(1~7)를 관리합니다. 점수 셀을 눌러 …"`
- After: `f"선수 이름과 실력 점수(1~{max_score})를 관리합니다. 점수 셀을 눌러 …"`

### 3. 하드코딩된 `max_value=7` 두 곳 → `max_score`

- [2_점수_관리.py:47](../../../app/pages/2_점수_관리.py#L47) "선수 추가" 폼의
  `number_input(..., max_value=7)` → `max_value=max_score`. 같은 줄 `value=4`(신규 추가
  시 프리필 점수)는 `max_score`보다 커지면 Streamlit이 에러를 내므로
  `value=min(default_score, max_score)`로 안전화한다(신규 선수 프리필로도 자연스럽다).
- [2_점수_관리.py:85](../../../app/pages/2_점수_관리.py#L85) `data_editor`의
  `NumberColumn(..., max_value=7)` → `max_value=max_score`.

### 설정 저장 시 검증

- `default_score`가 `max_score`를 초과하면 저장을 막고 에러를 표시한다.
- `max_score`를 현재보다 낮춰서 **기존에 그 값을 초과하는 점수를 가진 선수가 있으면**,
  저장은 허용하되 경고를 띄운다: "N명이 최고점(M)을 초과합니다: ...".
  **기존 점수는 자동으로 깎지 않는다** — 자동 하향은 되돌릴 수 없는 데이터 손실이다.
  저장된 초과 점수는 그대로 유지된다. (단 `data_editor`의 `max_value`가 새 상한이 되므로,
  초과 행은 이후 편집 시 검증에 걸릴 수 있다. 지금은 `max_score=7`로 기존 데이터와 일치해
  즉시 문제되지 않는다.)
- 저장 성공 시 기존 패턴(`st.session_state.score_action_msg` + `st.rerun()`)을 따른다.

`min_value=1`은 변경하지 않는다(최저점 조정은 요구 범위 밖).

## LLM 프롬프트 (B안)

[build_team_generator_base_prompt_section.py:28](../../../app/utils/build_team_generator_base_prompt_section.py#L28)의
하드코딩된 척도 의존 문구를 척도 무관하게 바꾼다. 숫자(2/5)는 제거하되 "극단값 선수를
특히 흩뿌려라"는 의도는 보존한다:

```
- 특정 점수대 편중 방지(특히 최고점·최저점에 가까운 극단 점수대 편중 방지)
```

이는 프롬프트 변경이므로 출력 품질에 미세한 영향이 있을 수 있으나(실제 LLM 실행으로만
확인 가능), 기존 의도를 최대한 보존하는 표현이다.

## 테스트 계획

기존 54개 통과가 베이스라인. `load_scores` 내부 표현 변경이 가장 위험하므로 여기에 집중한다.

1. **기존 회귀:** `test_save_scores.py`, `test_scores_github.py`의 기존 케이스는
   `load_scores()`/`save_scores()` 시그니처가 그대로이므로 통과해야 한다. 단, 내부에서
   파일 전체 dict를 다루도록 바뀌므로 로컬 테스트 픽스처의 파일 형태가 `{"scores": {...}}`
   래퍼를 유지하는지 확인한다.
2. **형제 키 보존 (핵심):** `settings`가 있는 파일에서 `save_scores(updates=...)`를 부른 뒤
   `settings`가 그대로 남아 있는지 검증(로컬·GitHub 양쪽). 반대로 `save_settings(...)` 후
   `scores`가 보존되는지도 검증.
3. **폴백:** `settings` 키가 없는 파일에서 `load_settings()`가 상수값을 반환하는지,
   일부 하위 키만 있을 때 개별 폴백되는지.
4. **main 주입:** `default_score` 하드코딩 제거 후에도 그래프 호출이 `load_settings()`의
   값을 주입하는지(기존 `RecordingFakeLLM` 픽스처 활용, 실 LLM 미사용).

## 범위 밖 (하지 않음)

- `min_value`(최저점) 설정화.
- 최고점 하향 시 기존 점수 자동 조정.
- score_fetch_node에서 default_score를 함께 읽어 GET 1회로 합치는 최적화.
- `max_score`를 LLM 프롬프트에 반영하는 것(현재 프롬프트는 척도 무관해짐).
