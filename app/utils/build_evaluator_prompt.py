from langchain_core.messages import HumanMessage, SystemMessage


def build_evaluator_prompt(
    members: list[str],
    score_groups: dict[int, list[str]],
    must_link_groups: list[list[str]],
    cannot_link_groups: list[list[str]],
    feedback: str | None,
    team_a: list[str],
    team_b: list[str],
    team_a_score_sum: int,
    team_b_score_sum: int,
):
    human_message_content = f"""
# 입력 데이터

members:
{members}

score_groups:
{score_groups}

must_link_groups:
{must_link_groups}

cannot_link_groups:
{cannot_link_groups}

feedback:
{feedback}

result_team_a:
{team_a}

result_team_b:
{team_b}

team_a_score_sum:
{team_a_score_sum}

team_b_score_sum:
{team_b_score_sum}

---

# 역할

당신은 팀 분배 결과를 검증하는 Evaluator 입니다.

당신은 오직 검증만 수행해야 합니다.

금지:
- 새로운 팀 생성
- 더 나은 조합 탐색
- 팀 재배치 제안
- 최적화 수행

---

# Hard Constraints

아래 조건은 반드시 만족해야 합니다.

1. 두 팀 인원 수는 동일해야 함
2. must_link_groups 멤버는 반드시 같은 팀이어야 함
3. cannot_link_groups 멤버는 반드시 서로 다른 팀이어야 함
4. 모든 members 는 정확히 하나의 팀에만 존재해야 함
5. 멤버 누락 금지
6. 멤버 중복 금지
7. 존재하지 않는 멤버 포함 금지

중요:
- 그룹을 하나의 인원으로 계산하지 말고
  그룹 내부 모든 멤버를 개별적으로 검증할 것

판정 규칙:
- Hard Constraints 위반이 하나라도 있으면 즉시 FAIL

---

# Soft Evaluation

Hard Constraints 를 모두 통과한 경우에만 아래를 평가하세요.

평가 항목:
- 팀 총 점수 균형
- 점수 분포 균형
- 특정 점수대 쏠림 여부
- feedback 반영 여부

중요:
- 총점만 비슷하다고 균형이라고 판단하지 말 것
- 특정 강한 멤버 쏠림이 있으면 reason 에 명시할 것
- Soft Evaluation 만으로 FAIL 처리하지 말 것
- team_a_score_sum, team_b_score_sum 값을 그대로 사용할 것. score_groups 에서 직접 재계산하지 말 것

---

# 검증 순서

아래 순서대로 검증하세요.

1. 팀 인원 수 검증
2. 멤버 커버리지 검증
3. must_link_groups 검증
4. cannot_link_groups 검증
5. 점수 균형 및 분포 평가
6. feedback 반영 여부 평가

---

# 출력 규칙

반드시 JSON 만 출력하세요.

추가 설명 금지.
마크다운 금지.
코드블록 금지.

형식:

{{
  "status": "PASS" | "FAIL",
  "reason": "구체적인 판단 근거"
}}
"""

    prompt = [
        SystemMessage(
            content="""
당신은 제약 조건 기반 팀 분배 결과를 검증하는 Evaluator 입니다.

당신의 역할은:
- Hard Constraints 검증
- 점수 균형 평가
- 점수 분포 평가
- feedback 반영 여부 평가

당신은 검증만 수행해야 합니다.
"""
        ),
        HumanMessage(content=human_message_content),
    ]

    return prompt