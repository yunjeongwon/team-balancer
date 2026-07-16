import os
from functools import lru_cache
from langchain.chat_models import init_chat_model

@lru_cache
def get_model():
    # 기본은 Gemini. Gemini를 못 쓸 때 USE_GPT=1 로 설정해 GPT로 대체
    use_gpt = os.environ.get("USE_GPT") == "1"
    return (
        init_chat_model(model="gpt-5-mini", model_provider="openai")
        if use_gpt
        else init_chat_model(model="gemini-3.1-flash-lite", model_provider="google_genai")
    )
