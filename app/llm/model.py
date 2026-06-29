from functools import lru_cache
from langchain.chat_models import init_chat_model

@lru_cache
def get_model():
    # return init_chat_model(model="claude-sonnet-4-6")
    # return init_chat_model(model="gpt-5-nano")
    return init_chat_model(model="gemini-2.5-flash-lite", model_provider="google_genai")