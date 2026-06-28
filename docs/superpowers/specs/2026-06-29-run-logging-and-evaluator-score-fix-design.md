# 런 로깅 + Evaluator 점수 합계 보완 + Placeholder 네이밍 정리

## 배경

현재 `input_node`, `score_fetch_node`, `team_generator_node`, `evaluator_node`는 진행 상황을 `print()`로만 출력한다. Streamlit을 실행한 터미널에만 남고 휘발되기 때문에, 특정 시도에서 evaluator가 왜 FAIL을 냈는지 나중에 다시 들여다볼 방법이 없다.

또한 evaluator는 두 팀의 점수 균형을 판단할 때 `score_groups`(점수별 멤버 목록)만 보고 스스로 합계를 계산해야 한다. 실제 운영 중 다음과 같이 evaluator가 자기 산술을 신뢰할 수 없는 수준으로 모순된 reason을 낸 사례가 있었다: 같은 문장 안에서 "조건은 만족합니다"라고 썼다가 "위반"이라 다시 쓰고, `score_diff=1`인 결과를 두고 "10점 이상 차이"라고 주장함. 팀 점수 합계를 코드에서 결정적으로 계산해 프롬프트에 명시적으로 제공하면 이 오류를 줄일 수 있다.

이 작업 중, 인원수를 짝수로 맞추기 위해 추가하는 placeholder 멤버의 이름이 `"EMPTY"`로 되어 있어 "점수가 없는/제외해야 할 멤버"로 오인하기 쉽다는 점도 함께 드러났다. 실제로는 `score_fetch_node`에서 다른 멤버와 동일하게 `default_score`를 받는, "평균 실력의 익명 참가자"를 의미하는 슬롯이며 최종 화면에만 표시되지 않는다. 이름을 의도에 맞게 정리한다.

## 목표

1. 각 팀 생성 실행(thread_id)의 전체 로그를 파일로 남겨, 콘솔이 닫힌 뒤에도 다시 확인할 수 있게 한다.
2. evaluator가 점수 균형을 판단할 때 코드가 계산한 정확한 팀별 점수 합계를 프롬프트로 받게 한다.
3. 인원수 패딩용 placeholder 멤버의 이름을 의도가 드러나도록 바꾸고, 한 곳(상수)에서만 정의되게 한다.

## 비목표

- Hard Constraint(인원수 일치, 멤버 누락/중복, must_link/cannot_link)를 코드에서 결정적으로 검증하는 것은 이번 범위에 포함하지 않는다. evaluator LLM이 계속 담당한다.
- team_generator 쪽 프롬프트(`build_team_generator_base_prompt_section.py`)에 점수 합계를 추가하는 것도 이번 범위 밖이다. evaluator만 다룬다.

## 설계

### 1. 실행 단위 파일 로깅

`app/logging_config.py`를 새로 만든다.

```python
import logging
from pathlib import Path

LOG_DIR = Path("logs")

def configure_run_logging(thread_id: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("team_balancer")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(LOG_DIR / f"{thread_id}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
```

- `LOG_DIR`을 모듈 변수로 노출해 테스트에서 `monkeypatch`로 임시 디렉터리를 가리키게 한다.
- `configure_run_logging`은 호출될 때마다 핸들러를 새로 구성한다. 같은 `thread_id`로 다시 호출되면(피드백 재시도) 같은 파일을 append 모드로 다시 열기 때문에 내용이 이어진다.

[main.py](/Users/jw_hyperwise/Documents/playground/team-balancer/app/main.py)에서 그래프를 `invoke`하기 직전 두 곳(신규 생성 시점, 피드백 resume 시점)에 `configure_run_logging(st.session_state.thread_id)`를 호출한다.

4개 노드 파일은 모듈 상단에 `logger = logging.getLogger("team_balancer")`를 두고, 기존 `print(...)`를 동일한 메시지로 `logger.info(...)`로 교체한다. 출력 내용은 그대로 유지한다(정보 손실 없음).

이 앱은 로컬 1인 사용을 전제로 하므로, 같은 프로세스에서 여러 브라우저 세션이 동시에 그래프를 실행하면 전역 logger의 핸들러가 서로 덮어쓸 수 있다는 점은 알려진 한계로 남기고 별도로 해결하지 않는다.

### 2. Evaluator 점수 합계 보완

`app/utils/compute_team_score_sum.py`를 새로 만든다.

```python
def compute_team_score_sum(team: list[str], member_scores: dict[str, int]) -> int:
    return sum(member_scores[member] for member in team)
```

Placeholder 멤버도 `member_scores`에 `default_score`로 들어 있으므로 특별 취급하지 않고 그대로 합산한다(아래 3번 참고).

[evaluator_node.py](/Users/jw_hyperwise/Documents/playground/team-balancer/app/graph/nodes/evaluator_node.py)에서 `team_a_score_sum`, `team_b_score_sum`을 계산해 로그로 남기고, [build_evaluator_prompt.py](/Users/jw_hyperwise/Documents/playground/team-balancer/app/utils/build_evaluator_prompt.py)에 새 인자로 전달한다. 프롬프트의 "입력 데이터" 섹션에 두 값을 추가하고, Soft Evaluation 지침에 "주어진 합계 값을 그대로 사용하고 score_groups에서 직접 재계산하지 말 것"을 추가한다.

### 3. Placeholder 멤버 네이밍 정리

`app/constants.py`를 새로 만든다.

```python
PLACEHOLDER_MEMBER = "(공석)"
```

다음 5곳의 `"EMPTY"` 리터럴을 `PLACEHOLDER_MEMBER`로 교체한다:

- [input_node.py:19](/Users/jw_hyperwise/Documents/playground/team-balancer/app/graph/nodes/input_node.py#L19) — 짝수 맞추기용 append
- [main.py:16-17](/Users/jw_hyperwise/Documents/playground/team-balancer/app/main.py#L16-L17) — 최종 화면 표시 시 제외하는 필터 2곳
- [tests/test_main_app.py](/Users/jw_hyperwise/Documents/playground/team-balancer/tests/test_main_app.py) — fixture 데이터, 어서션
- [tests/test_input_node.py](/Users/jw_hyperwise/Documents/playground/team-balancer/tests/test_input_node.py) — 어서션

`score_fetch_node`, `group_members_by_score`, `format_score_groups` 등 점수를 다루는 코드는 이름 문자열에 의존하지 않으므로 수정할 필요가 없다(grep으로 확인됨).

## 테스트

- `tests/conftest.py`에 autouse fixture를 추가해 `app.logging_config.LOG_DIR`을 `tmp_path`로 monkeypatch한다. 기존/신규 테스트가 실제 `logs/`를 건드리지 않게 한다.
- 신규: evaluator 프롬프트에 `team_a_score_sum`/`team_b_score_sum` 값이 포함되는지 `fake_llm.eval_prompts`로 검증 (`tests/test_team_generator_node.py`와 동일한 패턴).
- 신규: `configure_run_logging`이 thread_id별로 별도 파일을 만들고, 같은 thread_id로 재호출 시 내용이 append되는지 검증.
- 기존 EMPTY 관련 테스트 2개(`test_main_app.py`, `test_input_node.py`)를 `PLACEHOLDER_MEMBER` 상수 기준으로 갱신.

## 기타

- `.gitignore`에 `logs/` 추가 (멤버 실명이 들어간 로그라 커밋 대상이 아님).
