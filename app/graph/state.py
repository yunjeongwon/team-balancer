from typing import Annotated, TypedDict, Optional
from langgraph.graph import add_messages

class TeamState(TypedDict):
    messages: Annotated[list[str], add_messages]

    # Input
    raw_input: str
    members: list[str]

    # Data
    member_scores: dict[str, int]
    score_source: str  # (확장: DB / API 구분)

    # Output
    team_a: list[str]
    team_b: list[str]
    score_diff: int

    # Control
    approved: bool
    retry_count: int
    max_retries: int

    # Feedback
    feedback: Optional[str]

    # Debug / Trace (포트폴리오 중요)
    history: list[dict]  # 각 시도 결과 저장