from pydantic import BaseModel

class TeamSchema(BaseModel):
    team_a: list[str]
    team_b: list[str]
    score_diff: int