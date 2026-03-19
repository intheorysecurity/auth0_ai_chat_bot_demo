# HTTP API overview

Base URL: `http://localhost:8000` (or your deployment host).  
Protected routes expect `Authorization: Bearer <access_token>` unless noted.

## Auth

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/me` | Returns JWT claims for the current user (debug / `whoami` shortcut). |

## Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat/stream` | SSE stream: messages, optional tools, conversation id. |

## Conversations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/conversations` | List conversations for the user. |
| GET | `/api/conversations/{id}` | Load messages + tool events. |
| POST | `/api/conversations` | Create conversation. |
| DELETE | `/api/conversations/{id}` | Delete conversation. |

## Simulated commerce (`/api/data`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/data/products` | List products. |
| GET | `/api/data/products/{id}` | Product detail. |
| GET | `/api/data/orders` | List orders (FGA-filtered when configured). |
| GET | `/api/data/orders/{id}` | Order detail + FGA `can_read`. |
| POST | `/api/data/orders` | Create order (immediate; no CIBA—demo API). |
| POST | `/api/data/orders/{id}/cancel` | Cancel (FGA `can_write` when configured). |

## CIBA (optional)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ciba/start` | Start backchannel login (testing). |
| POST | `/api/ciba/poll` | Poll token; **creates order** when approved if a deferred checkout exists. |
| POST | `/api/ciba/pending/abandon` | Drop deferred checkout (e.g. UI timeout). |

## LLM helpers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/llm/ollama/models` | Lists local Ollama models (+ tool support flag). |

## MCP

MCP connection and OAuth callback routes live under `/api/mcp/*` (see `backend/app/main.py` for exact prefixes).

OpenAPI: visit `/docs` on the running FastAPI server for interactive schema.
