import os
from functools import lru_cache
from typing import Literal

from langchain.chat_models import init_chat_model

ModelRoute = Literal["gemini", "gemini_lite", "gpt"]


def get_default_model_route() -> ModelRoute:
    """환경 설정에 따른 최초 모델 경로를 반환한다."""
    if os.environ.get("USE_GPT") == "1":
        return "gpt"
    return "gemini"


@lru_cache
def get_model(route: ModelRoute | None = None):
    """지정한 모델 경로의 LLM을 반환한다."""
    route = route or get_default_model_route()

    if route == "gpt":
        return init_chat_model(model="gpt-5.6-luna", model_provider="openai")

    if route == "gemini":
        return init_chat_model(model="gemini-3.6-flash", model_provider="google_genai")

    if route == "gemini_lite":
        # 3.6 Flash가 과부하(503)일 때 받는 무료 예비. 구형이지만 응답이 안정적이다.
        return init_chat_model(model="gemini-3.5-flash-lite", model_provider="google_genai")

    raise ValueError(f"지원하지 않는 모델 경로입니다: {route}")
