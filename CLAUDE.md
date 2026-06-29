# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Project Notes: team-balancer

This is a solo project (LangGraph/Streamlit app that auto-balances futsal teams). No team to review PRs.

- **Git workflow:** Work directly on `master`, push directly — no feature branches or PRs needed for normal work. Still confirm with the user before pushing or before creating a worktree/branch if one seems warranted.
- **Dependency drift:** `langgraph`/`langchain` were missing from `pyproject.toml` once and silently broke the app under `uv run`. If something "doesn't work as intended," verify imports actually resolve before assuming the graph logic is wrong.
- **LangGraph thread_id:** The checkpointer persists state per `thread_id`. Don't reuse the same `thread_id` across logically separate runs (e.g. a new "팀 생성" click with different members) — it silently inherits stale `feedback`/`team_a`/`team_b`/`evaluation_count` from the previous run.
- **Testing LLM-backed code:** Use the `RecordingFakeLLM` fixture in `tests/conftest.py` (monkeypatches `app.graph.builder.get_model`) instead of calling a real LLM in tests.