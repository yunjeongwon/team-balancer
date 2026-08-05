import os
from functools import lru_cache
from typing import Literal

from langchain.chat_models import init_chat_model

ModelRoute = Literal["omniroute", "gemini", "gpt"]


def get_default_model_route() -> ModelRoute:
    """환경 설정에 따른 최초 모델 경로를 반환한다."""
    if os.environ.get("USE_GPT") == "1":
        return "gpt"
    if os.environ.get("OMNIROUTE_BASE_URL"):
        return "omniroute"
    return "gemini"


@lru_cache
def get_model(route: ModelRoute | None = None):
    """지정한 모델 경로의 LLM을 반환한다."""
    route = route or get_default_model_route()

    if route == "gpt":
        return init_chat_model(model="gpt-5.6-luna", model_provider="openai")

    if route == "gemini":
        return init_chat_model(model="gemini-3.5-flash-lite", model_provider="google_genai")

    if route == "omniroute":
        omniroute_base_url = os.environ.get("OMNIROUTE_BASE_URL")
        omniroute_api_key = os.environ.get("OMNIROUTE_API_KEY")
        if not omniroute_base_url or not omniroute_api_key:
            raise RuntimeError(
                "OmniRoute를 사용하려면 OMNIROUTE_BASE_URL과 OMNIROUTE_API_KEY를 설정해야 합니다."
            )

        return init_chat_model(
            model=os.environ.get("OMNIROUTE_MODEL", "auto"),
            model_provider="openai",
            base_url=omniroute_base_url.rstrip("/"),
            api_key=omniroute_api_key,
        )

    raise ValueError(f"지원하지 않는 모델 경로입니다: {route}")
