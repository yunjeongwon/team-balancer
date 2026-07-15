# scores.json GitHub API 영속화 설계

**날짜:** 2026-07-12
**목표:** `data/scores.json`의 읽기/쓰기를 로컬 파일 시스템에서 GitHub Contents API(같은 repo)로 옮겨, Streamlit Community Cloud(ephemeral 파일 시스템) 환경에서도 점수 변경이 유지되도록 한다.

## 배경

Streamlit Community Cloud는 ephemeral 파일 시스템을 사용한다. 앱이 재시작/재배포되면 컨테이너가 git repo에서 다시 clone되므로, 런타임에 `scores.json`에 쓴 변경은 모두 날아간다. 공식 문서도 "데이터를 세션 너머로 유지하려면 외부 데이터 소스에 연결하라"고 권장한다.

현재 구조:
- `app/utils/load_scores.py::load_scores()` — 로컬 파일에서 JSON 읽기
- `app/utils/load_scores.py::save_scores(dict)` — 임시 파일 + `os.replace` 원자적 쓰기
- `app/pages/2_점수_관리.py` — CRUD 페이지, 위 두 함수만 호출
- `app/graph/nodes/score_fetch_node.py` — `load_scores()` 호출

이들 호출부는 함수 시그니처(`load_scores()->dict`, `save_scores(dict)->None`)만 유지되면 변경하지 않아도 된다.

## 범위 (In scope)

- `load_scores`/`save_scores` 내부를 토큰 유무에 따라 로컬 파일 / GitHub API로 분기
- GitHub Contents API 호출 로직 (GET 읽기, PUT 쓰기 with SHA)
- `GITHUB_TOKEN` 설정 (로컬 `.env`, Cloud secrets)
- `requests` 의존성 명시 추가
- GitHub 백엔드에 대한 단위 테스트 (requests 모킹)
- 마이그레이션: `data/scores.json`은 git에 tracked로 유지

## 범위 외 (Out of scope)

- `data/scores.json`을 git에서 제거(gitignore) — 하지 않음. 이 파일이 API가 읽고 쓰는 원격 데이터이므로 tracked 유지.
- 외부 DB(Postgres/Supabase) 또는 Gist로의 대체 저장소 — 별도 설계 필요 시에만.
- 다중 편집자 동시 편집 충돌 해결 — 단일 편집자(비밀번호 게이트 뒤) 가정.
- 점수 변경 이력/감사 로그, 변경 알림.

## 결정된 접근법

1. **저장소 = 같은 repo의 `data/scores.json`.** 새 인프라·계정 없이 기존 커밋된 36명 데이터를 그대로 출발점으로 쓴다.
2. **구현 = `requests`로 Contents API 직접 호출.** API가 단순(GET/PUT, base64, SHA)해 래퍼 라이브러리(PyGithub) 불필요. 의존성 추가를 `requests` 하나로 최소화.
3. **분기 정책 = 토큰 유무 자동 분기.** `GITHUB_TOKEN`이 환경에 있으면 API, 없으면 기존 로컬 파일 로직. 로컬 개발·기존 테스트가 토큰 없이도 그대로 작동한다.
4. **토큰 = Fine-grained, 이 repo에만 `Contents: Read and Write`.** Public repo이므로 과도한 권한을 주지 않는다.

## 컴포넌트

### A. 영속성 계층 — `app/utils/load_scores.py` (기존 파일 확장)

`load_scores()` / `save_scores()` 시그니처는 유지하고, 내부에서 백엔드를 분기한다.

```python
# 상수
OWNER = "yunjeongwon"
REPO = "team-balancer"
SCORES_PATH = "data/scores.json"
BRANCH = "scores-data"
COMMIT_MESSAGE = "chore(scores): update via app"

def _get_token() -> str | None:
    """os.environ 우선, 없으면 st.secrets. 둘 다 없으면 None.
    auth.py 의 APP_PASSWORD 패턴과 동일."""

def load_scores() -> dict[str, int]:
    """_get_token()이 있으면 GitHub API, 없으면 로컬 파일."""

def save_scores(scores: dict[str, int]) -> None:
    """동일 분기. API 모드에서는 PUT(새 커밋) 생성."""
```

내부 헬퍼 (private):
```python
def _load_local() -> dict[str, int]: ...      # 기존 load_scores 본문
def _save_local(scores) -> None: ...          # 기존 save_scores 본문
def _load_github() -> dict[str, int]: ...     # GET contents → base64 decode → JSON
def _save_github(scores) -> None: ...         # GET sha → base64 encode → PUT
```

### B. 설정 — token

- **로컬**: `.env`에 `GITHUB_TOKEN=<fine-grained-token>` 추가 (`.env`는 이미 gitignored).
- **Cloud**: Streamlit 대시보드 → Settings → Secrets에 `GITHUB_TOKEN="<token>"` 추가.
- **토큰 발급**: GitHub → Settings → Developer settings → Fine-grained tokens → `yunjeongwon/team-balancer` 선택, 권한 `Contents: Read and Write`.

## 데이터 흐름

```
[배포: 토큰 有]                              [로컬: 토큰 無]
load_scores()                                load_scores()
  → _get_token() != None                       → _get_token() is None
  → _load_github()                             → _load_local()
  → GET /contents/data/scores.json             → open(data/scores.json)
  → base64 decode → JSON → dict                → json.load → dict

save_scores(dict)                             save_scores(dict)
  → _get_token() != None                       → _get_token() is None
  → _save_github(dict)                         → _save_local(dict)
  → GET sha (최신)                             → tmp + os.replace
  → base64 encode(dict) + sha
  → PUT /contents/data/scores.json (새 커밋)
```

## GitHub Contents API 상세

**헤더(공통):**
```
Authorization: token {token}
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
```

**읽기** — `GET https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}`
- 응답 `content`(base64)를 디코드 → UTF-8 JSON 파싱 → `data["scores"]` 반환.
- 응답 `sha`는 쓰기용 낙관적 락에 사용.

**쓰기** — `PUT https://api.github.com/repos/{owner}/{repo}/contents/{path}`
1. 먼저 GET으로 최신 `sha` 조회 (캐시 없이 매번 조회 → stale 위험 제거, 단일 편집자라 호출 비용 무시 가능).
2. 본문:
   ```json
   {"message": "chore(scores): update via app",
    "content": "<base64 of {"scores": {...}}>",
    "sha": "<조회한 sha>",
    "branch": "scores-data"}
   ```
3. 응답 200/201 확인. 실패 시 예외 발생.

## 에러 처리 & 동시성

- API 실패(네트워크/401 인증/403 권한/레이트리밋) → 예외 그대로 전파 → `2_점수_관리.py`의 기존 `try/except`가 잡아 `st.error` 표시. **추가 에러 코드 없음.**
- 409 Conflict(동시 편집, SHA 불일치) → 단일 편집자라 사실상 발생하지 않음. 발생 시 일반 에러로 노출.
- 토큰 누락 경고: API 모드가 아닐 때(로컬) save가 조용히 로컬 파일에 쓰므로, 로컬 변경이 Cloud에 반영되지 않을 수 있음은 분기 정책상 감수(개발 환경).

## 커밋 정책

- 매 `save_scores()` 호출 = GitHub에 자동 커밋 1건, 메시지 고정 `"chore(scores): update via app"`.
- 점수 변경 이력이 git 히스토리에 누적되는 것은 이 방식의 합의된 비용(저장소 = repo).

## 의존성

- `requests`를 `pyproject.toml`의 `[project.dependencies]`에 **명시 추가**.
  - 현재 streamlit의 transitive 의존으로 2.33.1이 깔려 있으나, 우리가 직접 import하므로 명시해야 의존성 drift를 막는다(CLAUDE.md 경고).

## 테스트 계획 (TDD)

**기존 `tests/test_save_scores.py`** — 로컬 백엔드, `tmp_path` 기반. 토큰이 없으면 자동으로 로컬 분기되므로 **수정 없이 통과**해야 한다.

**신규 `tests/test_scores_github.py`** — GitHub 백엔드:
- `_load_github`: `requests.get`을 monkeypatch → 가짜 base64 응답 → 디코드된 dict 반환 검증.
- `_save_github`: `requests.get`(sha) + `requests.put`을 monkeypatch → PUT 본문에 올바른 base64·sha·branch·message 포함 검증.
- 분기: `_get_token()`이 `None`이면 `_load_local`/`_save_local` 호출, 값이 있으면 `_load_github`/`_save_github` 호출 (monkeypatch로 각 backend를 spy).

`RecordingFakeLLM`(`tests/conftest.py`)과 동일한 monkeypatch 패턴을 사용한다.

## 영향 분석

- `app/utils/load_scores.py`: 내부 리팩터(함수 분할 + 분기 + GitHub 헬퍼 추가). 공개 시그니처 유지.
- `app/pages/2_점수_관리.py`: 변경 없음 (`load_scores`/`save_scores` 그대로 호출).
- `app/graph/nodes/score_fetch_node.py`: 변경 없음 (`load_scores()` 그대로). `"score_source": "data/scores.json"` → `"github:data/scores.json"` 정도로 정확화(선택적, 사소).
- `pyproject.toml`: `requests` 의존성 추가.
- `data/scores.json`: 구조·추적 상태 변경 없음.
- 기존 테스트: 로컬 분기로 인해 통과 유지.

## 마이그레이션

1. `load_scores.py` 리팩터 + GitHub 헬퍼 추가.
2. `pyproject.toml`에 `requests` 추가, `uv sync`.
3. `tests/test_scores_github.py` 추가.
4. Fine-grained token 발급 → `.env` 추가 (로컬).
5. Streamlit Cloud Secrets에 동일 token 추가.
6. 재배포 후 CRUD 동작·새로고침 후 데이터 유지 확인.
