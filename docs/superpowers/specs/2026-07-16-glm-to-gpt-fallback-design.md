# GLM → GPT 폴백 전환 설계

## 배경

`app/llm/model.py`의 `get_model()`은 현재 기본 GLM(`glm-5.2` via Z.AI Anthropic 호환 엔드포인트), `USE_GEMINI=1` 시 Gemini를 반환한다. Z.AI/GLM 의존을 제거하고 GPT(OpenAI)를 2순위 수동 스위치로 도입하며, **Gemini를 1순위(기본)** 로 올린다.

## 결정 사항

- **1순위(기본):** Gemini `gemini-3.1-flash-lite`
- **2순위:** `USE_GPT=1` 환경변수 설정 시 GPT `gpt-5-mini`
- **자동 폴백 미도입** — 한도 초과 시 자동 전환은 운영 가시성을 해치므로, 운영자가 수동으로 `USE_GPT` 스위치 (사용자 확인 완료)
- **GPT 모델 `gpt-5-mini`** ($0.25/$2.00 per 1M input/output) — 팀 밸런서는 `TeamSchema`/`EvaluationSchema` 구조화 출력이 필요해 추론 품질이 중요. `gpt-5-nano`보다 비용은 높지만 품질 균형이 안전 (사용자가 추천안 선택)
- **`langchain-anthropic` 의존성 제거** — GLM만 사용 중이었으므로 미사용. `langchain-openai`는 이미 `pyproject.toml`에 존재

## 변경 파일

1. **`app/llm/model.py`** — 로직 역전. GLM/Z.AI 분기(`base_url`, `api_key` 직접 전달) 제거. `OPENAI_API_KEY`/`GOOGLE_API_KEY`는 langchain이 env에서 자동 읽음.
   ```python
   @lru_cache
   def get_model():
       use_gpt = os.environ.get("USE_GPT") == "1"
       return (
           init_chat_model(model="gpt-5-mini", model_provider="openai")
           if use_gpt
           else init_chat_model(model="gemini-3.1-flash-lite", model_provider="google_genai")
       )
   ```
2. **`pyproject.toml`** — `langchain-anthropic` 제거 후 `uv lock` 갱신
3. **`README.md`** — 환경변수/스위치 안내 갱신 (`ZAI_API_KEY`/`USE_GEMINI` → `OPENAI_API_KEY`/`GOOGLE_API_KEY` + `USE_GPT`)
4. **`CLAUDE.md`** — 확인 결과 GLM/`USE_GEMINI` 직접 언급이 없어 변경 불필요 (원래 계획에서 제외)

## 환경변수

- `GOOGLE_API_KEY` (Gemini 기본용), `OPENAI_API_KEY` (GPT 스위치용) — langchain이 env 자동 읽음
- `USE_GPT` (선택, `=1` 시 GPT)
- `ZAI_API_KEY` 제거
- `.env`는 `.gitignore` 추적 대상 → 사용자가 로컬에서 직접 설정

## 테스트

- `tests/conftest.py`의 `RecordingFakeLLM` fixture가 `app.graph.builder.get_model`을 monkeypatch → 실제 모델 호출이 일어나지 않으므로 기존 테스트는 영향 없이 그대로 통과해야 함
- 검증: `uv run pytest` 전체 통과

## Out of scope

- 자동 폴백 / 재시도 / 에러 분기 로직
- `gpt-5-nano` 도입 (비용 절대치를 더 줄이려면 향후 별도 스위치)
- `lru_cache` 재설계 (`USE_GPT`는 프로세스 시작 시 고정이므로 호환)
