from functools import lru_cache
from langchain.chat_models import init_chat_model

@lru_cache
def get_model(use_gpt: bool = False):
    # 기본은 Gemini. USE_GPT=1 또는 세션 전환 시 GPT 사용.
    if use_gpt:
        return init_chat_model(model="gpt-5-mini", model_provider="openai")
    return init_chat_model(model="gemini-3.1-flash-lite", model_provider="google_genai")
