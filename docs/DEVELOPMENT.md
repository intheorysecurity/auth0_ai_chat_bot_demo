# Development

## Prerequisites

- Node.js **20+**
- Python **3.11+**
- Auth0 tenant (for full auth flow)
- At least one of: Anthropic API key, OpenAI API key, or [Ollama](https://ollama.com/) local

## Local setup (quick)

```bash
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
# Edit both files with your Auth0 app, API identifier, and keys.

cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

cd ../frontend && npm install && npm run dev
```

Open `http://localhost:3000`.

## Docker Compose

```bash
# Requires backend/.env and frontend/.env.local to exist (compose uses env_file).
docker compose up --build
```

- Backend: `8000`
- Frontend: `3000`
- Ollama: `11434`

If `env_file` paths are missing, Compose will error—create the files from the `*.example` templates first.

## Code quality

| Stack | Suggested command |
|-------|-------------------|
| Frontend | `cd frontend && npm run lint` (if configured) && `npx tsc --noEmit` |
| Backend | Format with [Ruff](https://docs.astral.sh/ruff/) or `python -m compileall app` |

## Troubleshooting

| Symptom | Check |
|--------|--------|
| CORS errors | `FRONTEND_URL` in `backend/.env` matches the Next.js origin. |
| 401 on API | `AUTH0_AUDIENCE` matches between frontend and backend; token includes `aud`. |
| FGA write 400 | Request body must not send empty `deletes.tuple_keys` (handled in client). |
| CIBA `login_hint` | Must be JSON `iss_sub` format (built by `ciba/service.py`). |
| Ollama duplicate tool ids | Provider uses UUIDs per tool call (`backend/app/llm/ollama.py`). |

## Git hygiene

- Never commit `backend/.env`, `frontend/.env.local`, or real `*.db` with sensitive data.
- Rotate any credential that has appeared in a commit or public issue.

See [SECURITY.md](../SECURITY.md).

## Before `git push`

```bash
git status
```

Confirm you are **not** committing:

- `backend/.env`, `frontend/.env.local`
- `backend/.venv/`, `node_modules/`, `frontend/.next/`
- `*.db` files with real data

If a secret was committed, rotate it and use `git filter-repo` or BFG to purge history before making the repo public.
