from langchain_core.messages import HumanMessage, SystemMessage
from app.graph.state import TeamState

def formmater_node(state: TeamState, llm) -> TeamState:
    team_a = state["team_a"]
    team_b = state["team_b"]

    prompt = [
        SystemMessage(content='당신은 출력 포맷을 정확하게 지키는 데 특화된 프롬프트 엔지니어이자 텍스트 포맷팅 전문가입니다.'),
        HumanMessage(content=f"""
        ### 지시사항
주어진 team_a와 team_b 데이터를 기반으로 팀을 지정된 형식에 맞게 출력하세요.

- team_a는 반드시 "🔵 블루팀"으로 변환
- team_b는 반드시 "🟡 골드팀"으로 변환
- 각 팀의 구성원은 한 줄에 공백으로 구분하여 나열
- 불필요한 설명, 추가 문장, 주석 절대 금지
- 오직 결과 포맷만 출력

### 출력 형식 (반드시 동일하게 유지)
🔵 블루팀
{{team_a 멤버들을 공백으로 나열}}

🟡 골드팀
{{team_b 멤버들을 공백으로 나열}}

### 입력 데이터
team_a:
{team_a}

team_b:
{team_b}

### 예시
🔵 블루팀
김동혁 전형준 김형욱 변석모 박종민 양창온 선윤호 김상래

🟡 골드팀
김한주 권진현 윤성빈 홍철민 김성인 권순우 안영찬 최한성

### 중요 규칙
- 줄바꿈 위치 반드시 유지
- 팀 이름 앞 이모지 포함 필수
- 결과 외 다른 텍스트 출력 금지
        """)
        ]

    res = llm.invoke(prompt)

    return {
        "messages": [res]
    }