from app.llm import model as model_mod


def _spy_init(monkeypatch, calls):
    def fake_init(model, model_provider, **kwargs):
        calls.append({"model": model, "model_provider": model_provider, **kwargs})
        return object()

    monkeypatch.setattr(model_mod, "init_chat_model", fake_init)


def test_get_model_uses_gemini_by_default(monkeypatch):
    calls = []
    _spy_init(monkeypatch, calls)
    monkeypatch.delenv("USE_GPT", raising=False)
    model_mod.get_model.cache_clear()

    model_mod.get_model()

    assert calls[-1] == {"model": "gemini-3.6-flash", "model_provider": "google_genai"}


def test_get_model_uses_gemini_lite_route(monkeypatch):
    calls = []
    _spy_init(monkeypatch, calls)
    model_mod.get_model.cache_clear()

    model_mod.get_model("gemini_lite")

    assert calls[-1] == {"model": "gemini-3.5-flash-lite", "model_provider": "google_genai"}


def test_get_model_uses_gpt_route(monkeypatch):
    calls = []
    _spy_init(monkeypatch, calls)
    model_mod.get_model.cache_clear()

    model_mod.get_model("gpt")

    assert calls[-1] == {"model": "gpt-5.6-luna", "model_provider": "openai"}


def test_default_route_ignores_leftover_omniroute_setting(monkeypatch):
    """OmniRoute는 제거됐다. 배포 secret에 값이 남아 있어도 Gemini부터 시작해야 한다."""
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.delenv("USE_GPT", raising=False)

    assert model_mod.get_default_model_route() == "gemini"


def test_default_route_uses_gpt_when_forced(monkeypatch):
    monkeypatch.setenv("USE_GPT", "1")

    assert model_mod.get_default_model_route() == "gpt"
