from pydantic import BaseModel, Field

class TeamSchema(BaseModel):
    team_a: list[str] = Field(description="팀a의 팀워들")
    team_b: list[str] = Field(description="팀b의 팀워들")
    score_diff: int = Field(description="팀 점수차")