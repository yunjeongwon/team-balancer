from app.llm import model as model_mod


def _spy_init(monkeypatch, calls):
    def fake_init(model, model_provider, **kwargs):
        calls.append({"model": model, "model_provider": model_provider, **kwargs})
        return object()

    monkeypatch.setattr(model_mod, "init_chat_model", fake_init)


def test_get_model_uses_gemini_by_default(monkeypatch):
    calls = []
    _spy_init(monkeypatch, calls)
    monkeypatch.delenv("OMNIROUTE_BASE_URL", raising=False)
    monkeypatch.delenv("OMNIROUTE_API_KEY", raising=False)
    monkeypatch.delenv("USE_GPT", raising=False)
    model_mod.get_model.cache_clear()

    model_mod.get_model()

    assert calls[-1] == {"model": "gemini-3.5-flash-lite", "model_provider": "google_genai"}


def test_get_model_uses_gpt_route(monkeypatch):
    calls = []
    _spy_init(monkeypatch, calls)
    model_mod.get_model.cache_clear()

    model_mod.get_model("gpt")

    assert calls[-1] == {"model": "gpt-5.6-luna", "model_provider": "openai"}


def test_get_model_uses_omniroute_when_configured(monkeypatch):
    calls = []
    _spy_init(monkeypatch, calls)
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "https://llm.example.com/v1/")
    monkeypatch.setenv("OMNIROUTE_API_KEY", "omniroute-key")
    monkeypatch.setenv("OMNIROUTE_MODEL", "team-balancer-free-first")
    model_mod.get_model.cache_clear()

    model_mod.get_model("omniroute")

    assert calls[-1] == {
        "model": "team-balancer-free-first",
        "model_provider": "openai",
        "base_url": "https://llm.example.com/v1",
        "api_key": "omniroute-key",
    }


def test_get_model_requires_gateway_key_when_omniroute_is_configured(monkeypatch):
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.delenv("OMNIROUTE_API_KEY", raising=False)
    model_mod.get_model.cache_clear()

    try:
        model_mod.get_model("omniroute")
    except RuntimeError as error:
        assert "OMNIROUTE_API_KEY" in str(error)
    else:
        raise AssertionError("OmniRoute 키 누락 시 오류가 발생해야 합니다.")


def test_default_route_uses_omniroute_when_configured(monkeypatch):
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.delenv("USE_GPT", raising=False)

    assert model_mod.get_default_model_route() == "omniroute"


def test_default_route_uses_gpt_when_forced(monkeypatch):
    monkeypatch.setenv("USE_GPT", "1")
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "https://llm.example.com/v1")

    assert model_mod.get_default_model_route() == "gpt"
