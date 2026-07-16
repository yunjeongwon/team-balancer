from app.llm import model as model_mod


def _spy_init(monkeypatch, calls):
    def fake_init(model, model_provider):
        calls.append({"model": model, "model_provider": model_provider})
        return object()

    monkeypatch.setattr(model_mod, "init_chat_model", fake_init)


def test_get_model_uses_gemini_by_default(monkeypatch):
    calls = []
    _spy_init(monkeypatch, calls)
    model_mod.get_model.cache_clear()

    model_mod.get_model(use_gpt=False)

    assert calls[-1] == {"model": "gemini-3.1-flash-lite", "model_provider": "google_genai"}


def test_get_model_uses_gpt_when_use_gpt_true(monkeypatch):
    calls = []
    _spy_init(monkeypatch, calls)
    model_mod.get_model.cache_clear()

    model_mod.get_model(use_gpt=True)

    assert calls[-1] == {"model": "gpt-5-mini", "model_provider": "openai"}
