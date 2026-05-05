from langchain_core.messages import HumanMessage, SystemMessage
from app.graph.state import TeamState

def evaluator_node(state: TeamState, structured_llm) -> TeamState:
    member_scores = state["member_scores"]
    team_a = state["team_a"]
    team_b = state["team_b"]
    feedback = state.get("feedback", "")
    evaluation_count = state.get("evaluation_count", 0)

    prompt = [
        SystemMessage(content="""
당신은 **공정한 팀 분배 알고리즘 검증 전문가(Evaluator)**입니다.  
당신의 역할은 생성된 팀 결과가 **정해진 규칙과 목표를 얼마나 잘 만족하는지 합리적이고 현실적인 기준으로 검증**하는 것입니다.  
단, 과도하게 엄격한 기준이 아닌 **실제 최적화 가능성 및 제약 조건을 고려한 유연한 평가**를 수행해야 합니다.
        """),
        HumanMessage(content=f"""
### 입력
다음 정보가 주어집니다:

1. member_scores:
{member_scores}
- 형식: dict[str, int]
- 각 팀원의 가중치 정보

2. team_a:
{team_a}

3. team_b:
{team_b}

4. (선택) feedback:
{feedback}

---

### 검증 목표

아래 기준을 종합적으로 평가하여 결과를 **PASS 또는 FAIL**로 판단하세요.

---

### 핵심 검증 기준

#### 1. 전체 가중치 합 균형 (완화 기준 적용)
- 두 팀의 총합 차이(score_diff)가 **1 이하이면 PASS로 간주**
- score_diff가 2 이상일 경우 FAIL
- 단, 분포가 매우 불균형한 경우는 예외적으로 FAIL 가능

#### 2. 가중치 분포 균형 (현실적 기준 적용)
- 동일 가중치가 양 팀에 "가능한 범위 내에서" 고르게 분배되었는가?
- 특정 가중치가 한쪽에 몰려 있어도,
  → **해당 가중치의 전체 개수가 홀수이거나 구조적으로 분배 불가능한 경우는 PASS 가능**
- 단, 명백히 더 나은 분배가 존재하면 FAIL

#### 3. 분배 전략 검증
- 극단적인 고점/저점 쏠림이 있는가?
- 단순 greedy 결과라도 결과가 충분히 균형적이면 PASS 가능

#### 4. 인원 수 균형
- 인원 수 차이가 1 이하이면 PASS

#### 5. 전체 커버리지
- 모든 멤버가 정확히 한 팀에만 포함되어야 함
- 중복 또는 누락 발생 시 즉시 FAIL

#### 6. 피드백 반영 여부 (선택)
- feedback이 있을 경우 반드시 반영 여부 평가
- 없으면 해당 항목은 무시

---

### 평가 시 중요 원칙

- **"이론적 완벽함"이 아니라 "현실적 최적" 기준으로 평가**
- 구조적으로 개선 불가능한 경우 PASS 허용
- score_diff ≤ 1이면 기본적으로 긍정적으로 판단
- 분포 불균형이 있어도 **개선 여지가 없으면 PASS**
- 단, 명확한 개선 가능성이 있으면 FAIL

---

### 평가 절차

1. team_a / team_b 총 점수 계산
2. score_diff 계산
3. 가중치별 분포 비교
4. 구조적으로 개선 가능한지 판단
5. 최종 PASS / FAIL 결정

---

### 출력 형식 (엄격 준수)

반드시 아래 JSON 형태로만 응답하세요:

{{
  "status": "PASS" | "FAIL",
  "reason": "판단 근거 (구체적인 수치 + 개선 가능 여부 포함)"
}}

---

### 최종 지침

당신은 단순히 틀린 점을 찾는 평가자가 아니라,  
**현실적으로 더 나은 팀이 가능한지를 판단하는 균형 잡힌 품질 게이트**입니다.

불가능한 이상적인 기준으로 FAIL을 남발하지 말고,  
**합리적이고 납득 가능한 수준이면 PASS를 부여하세요.**
        """)]
    
    res = structured_llm.invoke(prompt)

    message = f"'{evaluation_count + 1}번째' 검증 완료"
    print(message)
    print(res)

    return {
        "messages": [message],
        "evaluation_status": res.status,
        "evaluation_reason": res.reason,
        "evaluation_count": evaluation_count + 1
    }
