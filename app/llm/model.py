import os
from functools import lru_cache
from langchain.chat_models import init_chat_model

@lru_cache
def get_model():
    # GLM 토큰이 다 떨어지면 USE_GEMINI=1 로 설정해 Gemini로 대체
    use_gemini = os.environ.get("USE_GEMINI") == "1"
    return (
        init_chat_model(model="gemini-2.5-flash-lite", model_provider="google_genai")
        if use_gemini
        else init_chat_model(
            model="glm-5.2",
            model_provider="anthropic",
            base_url="https://api.z.ai/api/anthropic",
            api_key=os.environ["ZAI_API_KEY"],
        )
    )