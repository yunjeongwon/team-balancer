from langchain_core.messages import HumanMessage, SystemMessage


def build_team_generator_prompt(
    score_groups: dict[int, list[str]],
    must_link_groups: list[list[str]],
    cannot_link_groups: list[list[str]],
    feedback: str | None,
    team_a: list[str] | None,
    team_b: list[str] | None,
    evaluation_reason: str | None = None,
):
    base_prompt_section = f"""
## 필수 규칙 (절대 위반 금지)

아래 규칙은 모두 반드시 만족해야 합니다.

1. team_a 와 team_b 의 인원 수는 반드시 동일해야 합니다.
2. must_link_groups 의 멤버는 반드시 같은 팀이어야 합니다.
3. cannot_link_groups 의 멤버는 반드시 서로 다른 팀이어야 합니다.

---

## 최적화 목표

필수 규칙을 모두 만족한 상태에서 아래 목표를 최대한 만족하세요.

- 특정 점수대 편중 방지(특히, 2점 이하와 5점 이상 더욱 편중 방지)
- 총 점수 차이 최소화

---

- 팀 구성은 유지한 채, 최종 출력 직전에 team_a 와 team_b 내부 멤버 순서만 랜덤 셔플하세요.

---

## 출력 형식

- team_a: list[str]
- team_b: list[str]
- score_diff: int
- reason: str

---

## 입력 데이터

### score_groups
{score_groups}

### must_link_groups
{must_link_groups}

### cannot_link_groups
{cannot_link_groups}
"""

    prompt_sections = [base_prompt_section]

    evaluation_reason_section = f"""
---

## 이전 시도 검증 실패 사유

아래 사유로 직전 시도가 검증을 통과하지 못했습니다. 이 문제를 해결하도록 다시 생성하세요.

### evaluation_reason
{evaluation_reason}

### previous_team_a
{team_a}

### previous_team_b
{team_b}
"""

    if evaluation_reason:
        prompt_sections.append(evaluation_reason_section)

    feedback_section = f"""
---

## 추가 수정 요청

이전 결과를 가능한 최소 수정으로 개선하세요.

### feedback
{feedback}

### previous_team_a
{team_a}

### previous_team_b
{team_b}
"""

    if feedback:
        prompt_sections.append(feedback_section)

    human_message_content = "\n".join(prompt_sections)

    prompt = [
        SystemMessage(content="""
당신은 제약 조건 기반 팀 분배 최적화 전문가입니다.
전체 인원을 2개의 팀으로 분배하세요.
        """),
        HumanMessage(content=human_message_content)
    ]

    return prompt