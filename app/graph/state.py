from typing import Annotated, Literal, TypedDict, Optional
from langgraph.graph import add_messages

class TeamState(TypedDict):
    messages: Annotated[list[dict], add_messages]

    # Input
    raw_input: str
    members: list[str]
    must_link_pairs: list[tuple[str, str]]
    cannot_link_pairs: list[tuple[str, str]]

    # Data
    member_scores: dict[str, int]
    score_source: str  # (확장: DB / API 구분)

    # Output
    team_a: list[str]
    team_b: list[str]
    score_diff: int

    # Eval
    evaluation_status: Literal["PASS", "FAIL"]
    evaluation_reason: str
    evaluation_count: int

    # Control
    approved: bool
    retry_count: int
    max_retries: int

    # Feedback
    feedback: Optional[str]

    # Debug / Trace
    history: list[dict]  # 각 시도 결과 저장