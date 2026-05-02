from langchain_core.messages import HumanMessage, SystemMessage
from app.graph.state import TeamState

def team_generator_node(state: TeamState, structured_llm) -> TeamState:
    member_scores = state["member_scores"]

    messages = [
        SystemMessage(content="""당신은 공정한 팀 분배 알고리즘 설계에 특화된 전문가입니다.  
주어진 데이터를 기반으로 **두 팀을 최대한 균형 있게 나누는 것**이 목표입니다."""),
        HumanMessage(content=f"""
        당신은 공정한 팀 분배 알고리즘 설계에 특화된 전문가입니다.  
주어진 데이터를 기반으로 **두 팀을 최대한 균형 있게 나누는 것**이 목표입니다.

### 입력 데이터
member_scores:
{member_scores}

- `member_scores: dict[str, int]`
  - key: 팀원 이름
  - value: 해당 팀원의 가중치(점수)

### 목표
- 모든 팀원을 두 개의 팀으로 나눈다.
- 두 팀의 **가중치 총합 차이(score_diff)**가 최소가 되도록 구성한다.

### 출력 형식
반드시 아래의 Pydantic 스키마를 따르는 structured output으로 반환한다:

class TeamSchema(BaseModel):
    team_a: list[str]
    team_b: list[str]
    score_diff: int

### 세부 요구사항
1. 모든 멤버는 반드시 한 팀에만 포함되어야 한다.
2. 두 팀 간 인원 수는 가능한 균형을 맞춘다.
3. 각 팀의 가중치 합 차이(score_diff)는 최소화한다.
4. 팀 구성이 완료된 후:
   - 각 팀 내부의 멤버 순서는 **완전히 랜덤하게 셔플**한다.
   - 가중치 기반으로 정렬된 흔적이 절대 보이지 않아야 한다.
5. score_diff는 절댓값 기준의 차이를 의미한다.

### 추가 지침
- 단순한 절반 분할이 아니라 **최적 또는 준최적 균형 분배**를 수행하라.
- 가능한 경우 더 나은 균형이 존재하는지 한 번 더 검토한 뒤 최종 결과를 반환하라.
- 출력은 반드시 TeamSchema 형태의 structured_output으로만 반환한다.
        """)
        ]

    res = structured_llm.invoke(messages)

    return {
        "team_a": res.team_a,
        "team_b": res.team_b,
        "score_diff": res.score_diff,
    }