from typing import Literal
from pydantic import BaseModel, Field

class EvaluationSchema(BaseModel):
    status: Literal["PASS", "FAIL"] = Field(description="평가 결과")
    reason: str = Field(description="판단 근거")