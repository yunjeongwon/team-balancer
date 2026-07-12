from app.utils import load_scores as ls


def test_get_token_prefers_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    assert ls._get_token() == "env-token"


def test_get_token_returns_none_when_absent(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # 테스트 컨텍스트에선 st.secrets 도 unavailable → None
    assert ls._get_token() is None


def test_headers_includes_authorization_and_accept(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    h = ls._headers()
    assert h["Authorization"] == "token abc"
    assert h["Accept"] == "application/vnd.github+json"
