# Repository Guidelines

## Project Structure & Module Organization
- `backend/`: Python 3.13 FastAPI backend scaffold (`main.py` entry point, `pyproject.toml` for deps). Grow it into `app/` packages with routers/services as outlined in `docs/02_Backend_Architecture.md`.
- `uni-app/`: UniApp frontend (Vue) with `App.vue`, `pages/`, `pages.json`, and shared styles in `uni.scss`. See `docs/03_Frontend_Architecture.md` for planned routes/components.
- `docs/`: Architecture and planning references (`00_Master_Plan.md` onward). Keep these in sync when behavior changes.

## Build, Test, and Development Commands
- Backend env: `python -m venv .venv && source .venv/bin/activate` (Windows: `.\.venv\Scripts\activate`).
- Backend deps: add packages with `pip install <pkg>` and record them in `backend/pyproject.toml` (`[project].dependencies`). Regenerate lockfiles if you add one.
- Run backend draft: `python backend/main.py` (replace with `uvicorn app.main:app --reload` once FastAPI is wired).
- UniApp dev: import `uni-app/` into HBuilderX or a UniApp CLI workspace; once a `package.json` exists, run `npm install && npm run dev:h5` (or target-specific scripts) from that folder.

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indents, type hints on functions, async-first for I/O. Group FastAPI routers under `app/api/<domain>.py`; services under `app/services/`.
- Vue/UniApp: Single File Components with `<script setup>` preferred; component files PascalCase; pages live under `pages/<feature>/`. Keep shared variables in `uni.scss`; favor CSS variables over magic values.
- Strings/secrets: never hardcode API keys; consume from env and document expected keys.

## Testing Guidelines
- Backend: prefer `pytest`; place tests in `backend/tests/test_*.py`. Include both unit (service helpers) and API-level tests (FastAPI `TestClient`). Aim to cover AI import, auth, and quiz flows.
- Frontend: add page-level tests with your chosen runner (e.g., Vitest + @vue/test-utils) once the toolchain is added; keep fixtures minimal and deterministic.
- Run: `pytest backend` once tests exist; add `npm run test` for frontend when configured. Document coverage expectations in PRs.

## Commit & Pull Request Guidelines
- No repo history yet; use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`) in present tense. Keep scopes small (`feat(api)`, `fix(ui)`).
- PRs should include: purpose summary, testing notes/commands run, affected routes/pages, screenshots or screen recordings for UI changes, and linked issues/tasks. Keep diffs minimal and align with the docs updates.

## Security & Configuration Tips
- Store secrets in env files excluded from VCS (add `.env.example` with placeholders). Never commit credentials or tokens.
- Validate all external inputs (upload payloads, text imports) before invoking AI services. Add timeouts/retries when calling remote AI endpoints. Log with care; avoid printing PII.***
