from langchain_core.messages import HumanMessage, SystemMessage
from app.graph.state import TeamState
from app.utils.build_base_prompt_section import build_base_prompt_section
from app.utils.build_feedback_section import build_feedback_section
from app.utils.format_groups import format_groups
from app.utils.format_score_groups import format_score_groups
from app.utils.format_team import format_team
from app.utils.group_members_by_score import group_members_by_score

def team_generator_node(state: TeamState, structured_llm) -> TeamState:
    members = state["members"]
    member_scores = state["member_scores"]
    team_a = state.get("team_a")
    team_b = state.get("team_b")
    must_link_groups = state["must_link_groups"]
    cannot_link_groups = state["cannot_link_groups"]
    feedback = state.get("feedback", "")

    formatted_score_groups = format_score_groups(group_members_by_score(
      members,
      member_scores,
    ))

    formatted_must_link_groups = format_groups(must_link_groups)
    formatted_cannot_link_groups = format_groups(cannot_link_groups)

    formatted_team_a = format_team(team_a)
    formatted_team_b = format_team(team_b)

    prompt_sections = [
        build_base_prompt_section(
            formatted_score_groups, 
            formatted_must_link_groups, 
            formatted_cannot_link_groups
        )
    ]

    if feedback:
        prompt_sections.append(
            build_feedback_section(
                feedback, 
                formatted_team_a, 
                formatted_team_b
            )
        )
    
    human_message_content = "\n".join(prompt_sections)

    prompt = [
        SystemMessage(content="""
당신은 **제약 조건이 있는 팀 분배 최적화 문제를 해결하는 전문가**입니다.  
단순한 합계 균형이 아니라, **가중치 분포의 균형 + 그룹 제약 조건을 모두 만족하는 팀 구성**을 생성하는 것이 목표입니다.  
또한, 필요 시 **사람의 피드백을 반영하여 결과를 개선**해야 합니다.
        """),
        HumanMessage(content=human_message_content)
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
        "output_reason": res.reason,
    }