# Architecture

## System context

```text
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Browser   │────▶│  Next.js (3000)  │────▶│ FastAPI (8000)  │
│  Auth0 SDK  │     │  Auth0 session   │     │  JWT validate   │
└─────────────┘     └──────────────────┘     └────────┬────────┘
                                                      │
                    ┌─────────────────────────────────┼────────────────────────┐
                    ▼                                 ▼                        ▼
             ┌─────────────┐                  ┌─────────────┐           ┌───────────┐
             │ LLM vendors │                  │ Auth0 FGA   │           │ Auth0     │
             │ Claude /    │                  │ OpenFGA API │           │ CIBA      │
             │ OpenAI /    │                  │ (optional)  │           │ (optional)│
             │ Ollama      │                  └─────────────┘           └───────────┘
             └─────────────┘
```

## Backend (`backend/app`)

| Area | Responsibility |
|------|----------------|
| `auth/` | Validate Bearer JWT (Auth0 / Okta). |
| `chat/` | SSE streaming chat, builtin tools (`list_orders`, `create_order`, …), MCP tool loop. |
| `conversations/` | SQLite persistence for threads + tool events. |
| `data/` | Simulated REST catalog & orders; FGA checks on read/write. |
| `fga/` | HTTP client for Check + Write (tuples omitted when empty deletes). |
| `ciba/` | Backchannel auth start/poll; pending checkout map until approval. |
| `llm/` | Provider adapters (Anthropic, OpenAI, Ollama). |
| `mcp_client/` | Connect to external MCP servers + OAuth where needed. |

## Frontend (`frontend/src`)

| Area | Responsibility |
|------|----------------|
| `app/chat/` | Chat page, model sidebar, conversation list. |
| `lib/hooks/useChat.ts` | SSE client, optional shortcuts (`whoami`, orders list). |
| `components/McpToolCall.tsx` | Renders tool results; auto-polls CIBA when `approval_required`. |
| `middleware.ts` | Auth0 route protection. |

## Security boundaries

- **Browser** never sees LLM vendor keys; only the backend uses them.
- **JWT** is sent to the API for protected routes; `sub` scopes simulated orders and FGA user ids (`user:{sub}`).
- **FGA** optional: when unset, order APIs are permissive (demo mode).
- **CIBA high-value path**: order row + FGA owner tuple are created **after** token poll succeeds, not when the challenge is sent.

## Data stores

| Store | Scope | Notes |
|-------|-------|------|
| SQLite (`DATABASE_URL`) | Conversations / messages / tool events | File lives under `backend/` by default. |
| In-memory `FakeDataStore` | Products & orders | Resets on process restart. |
| In-memory `_pending` (CIBA) | Deferred checkouts keyed by `auth_req_id` | Cleared on approve, deny, abandon, or timeout. |
