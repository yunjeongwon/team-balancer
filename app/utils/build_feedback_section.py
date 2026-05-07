def build_feedback_section(
    feedback: str,
    formatted_team_a: str,
    formatted_team_b: str,
) -> str:
    return f"""
### 추가 입력
feedback:
{feedback}

- 형식: str 또는 None
- 사람이 이전 결과에 대해 제공한 피드백

previous_team_a:
{formatted_team_a}

- 전에 만들어진 팀a 결과

previous_team_b:
{formatted_team_b}

- 전에 만들어진 팀b 결과
    """