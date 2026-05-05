from langchain_core.messages import HumanMessage, SystemMessage
from app.graph.state import TeamState

def team_generator_node(state: TeamState, structured_llm) -> TeamState:
    member_scores = state["member_scores"]
    feedback = state.get("feedback", "")

    prompt = [
        SystemMessage(content="""
당신은 **공정한 팀 분배 알고리즘 설계 전문가**입니다.  
단순한 합계 균형이 아니라, **가중치 분포까지 균형 잡힌 팀 구성**을 만드는 것이 목표입니다.  
또한, 필요 시 **사람의 피드백을 반영하여 결과를 개선**해야 합니다.
        """),
        HumanMessage(content=f"""
### 입력
member_scores:
{member_scores}

- 형식: dict[str, int]
  - key: 팀원 이름
  - value: 팀원의 가중치 (1 이상의 정수)

feedback (선택적 입력):
{feedback}

- 형식: str 또는 None
- 사람이 이전 결과에 대해 제공한 피드백
- 없을 수도 있음 (None 또는 빈 문자열)

---

### 핵심 목표
두 팀을 구성할 때 다음을 모두 만족해야 합니다:

1. **총 가중치 합 차이 최소화**
2. **가중치 분포의 균형 유지 (최우선)**
3. **(피드백이 존재할 경우) 피드백을 반영한 개선된 결과 생성**

---

### 핵심 로직 (반드시 준수)

#### 1. 가중치 분산 규칙
- 동일 가중치는 가능한 한 **양 팀에 균등 분배**한다.
- 예:
  - 1점 여러 명 → A/B 교차 배치
  - 2점, 3점, 4점, 5점 모두 동일 규칙 적용

#### 2. 대체 규칙 (Fallback)
- 특정 가중치가 한 팀에 몰리는 상황을 피해야 한다.
- 부족한 경우:
  - **가장 가까운 가중치로 대체 분산**
  - 예:
    - 1점 부족 → 2점으로 보완
    - 4점 부족 → 5점으로 보완

#### 3. 금지 사항
- 낮은 점수와 높은 점수를 극단적으로 분리하는 방식 금지
- 단순 합계 기반 greedy 분배 금지

---

### 추천 접근 방식 (강력 권장)

1. 가중치 기준 그룹화 (예: 1점 그룹, 2점 그룹 ...)
2. 각 그룹 내 **교차 분배 (alternating assignment)**
3. 초기 분배 후 합 차이를 비교
4. 필요 시 최소 swap으로 미세 조정
5. 최종 검증:
   - 합 차이 최소화
   - 분포 균형 유지

---

### 피드백 반영 규칙 (중요)

- feedback이 존재하는 경우:
  - 피드백을 분석하여 문제점을 파악
  - 기존 규칙을 유지하면서 **최소 수정으로 개선**
  - 피드백이 목표(공정성)를 해치는 경우에는 **부분적으로만 반영**

- feedback이 없는 경우:
  - 기본 로직만으로 최적 결과 생성

---

### 추가 요구사항

- 모든 멤버는 반드시 하나의 팀에만 속해야 한다
- 두 팀의 인원 수는 가능한 균형 유지
- 각 팀 내부 순서는 **완전히 랜덤 셔플**
- 결과 생성 후 **자체 검증 수행 (self-check)**
  - 더 나은 분배가 가능한지 한 번 더 점검

---

### 출력 형식 (반드시 준수)

다음 정보를 포함하여 반환:

- team_a: list[str]
- team_b: list[str]
- score_diff: int
- reasoning: (간단한 설명, 선택 사항)

---

### 최종 지침

- 항상 **분포 균형 > 합계 균형** 우선순위를 유지하라
- 피드백이 있다면 "개선된 결과"를 만들어야 한다
- 단순한 계산이 아닌 **전략적 분배 문제**로 접근하라
        """)
        ]

    res = structured_llm.invoke(prompt)

    message = f"팀 생성 완료"
    print(message)
    print(res)

    return {
        "messages": [message],
        "team_a": res.team_a,
        "team_b": res.team_b,
        "score_diff": res.score_diff,
    }