import time
from typing import Any

import anthropic
import httpx
import openai
from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.config import settings


router = APIRouter()

_CACHE_TTL_S = 60.0
_cache: dict[str, Any] = {
    "ts": 0.0,
    "base_url": "",
    "data": None,
}

_provider_cache: dict[str, Any] = {}


async def _list_ollama_models(client: httpx.AsyncClient) -> list[str]:
    resp = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
    resp.raise_for_status()
    data = resp.json() or {}
    models = data.get("models", [])
    names: list[str] = []
    if isinstance(models, list):
        for m in models:
            if not isinstance(m, dict):
                continue
            name = m.get("name") or m.get("model")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return sorted(set(names))


async def _supports_tools(client: httpx.AsyncClient, model: str) -> bool:
    # Fast heuristic: does Ollama accept the "tools" field for this model?
    # If it rejects with "does not support tools", treat it as false.
    payload = {
        "model": model,
        "stream": False,
        "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "noop",
                    "description": "No-op tool for capability detection.",
                    "parameters": {"type": "object", "additionalProperties": False},
                },
            }
        ],
    }
    resp = await client.post(f"{settings.ollama_base_url.rstrip('/')}/api/chat", json=payload)
    if resp.status_code == 400:
        try:
            err = (resp.json() or {}).get("error", "")
        except Exception:
            err = resp.text
        if "does not support tools" in str(err).lower():
            return False
        return False
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    return True


@router.get("/ollama/models")
async def ollama_models(user: dict = Depends(get_current_user)):
    _ = user  # endpoint is authenticated; user is not otherwise needed
    base_url = settings.ollama_base_url.rstrip("/")
    now = time.time()
    if (
        _cache["data"] is not None
        and _cache["base_url"] == base_url
        and (now - float(_cache["ts"])) < _CACHE_TTL_S
    ):
        return _cache["data"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        names = await _list_ollama_models(client)
        models = []
        for name in names:
            try:
                supports = await _supports_tools(client, name)
            except Exception:
                supports = False
            models.append({"name": name, "supports_tools": supports})

    data = {"models": models}
    _cache["ts"] = now
    _cache["base_url"] = base_url
    _cache["data"] = data
    return data


def _curated_openai_models() -> list[str]:
    # Conservative curated list; user can still type a custom model_id in the UI.
    return [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "o4-mini",
        "o3-mini",
    ]


def _curated_claude_models() -> list[str]:
    return [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
    ]


def _cache_get(key: str, ttl_s: float = 60.0) -> Any | None:
    now = time.time()
    item = _provider_cache.get(key)
    if not item:
        return None
    if (now - float(item.get("ts", 0.0))) > ttl_s:
        return None
    return item.get("data")


def _cache_set(key: str, data: Any) -> None:
    _provider_cache[key] = {"ts": time.time(), "data": data}


@router.get("/openai/models")
async def openai_models(user: dict = Depends(get_current_user)):
    _ = user
    cached = _cache_get("openai_models")
    if cached is not None:
        return cached

    models = _curated_openai_models()
    source = "curated"

    if settings.openai_api_key:
        try:
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            resp = await client.models.list()
            ids: list[str] = []
            for m in getattr(resp, "data", []) or []:
                mid = getattr(m, "id", None)
                if isinstance(mid, str):
                    ids.append(mid)
            # Prefer chat-capable naming patterns.
            ids = sorted(
                {i for i in ids if i.startswith(("gpt-", "o", "chatgpt-"))}
            )
            if ids:
                models = ids
                source = "api"
        except Exception:
            pass

    data = {"models": [{"id": m} for m in models], "source": source}
    _cache_set("openai_models", data)
    return data


@router.get("/claude/models")
async def claude_models(user: dict = Depends(get_current_user)):
    _ = user
    cached = _cache_get("claude_models")
    if cached is not None:
        return cached

    models = _curated_claude_models()
    source = "curated"

    if settings.anthropic_api_key:
        try:
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            # Not all SDK versions support listing; fall back gracefully.
            resp = await client.models.list()  # type: ignore[attr-defined]
            ids: list[str] = []
            for m in getattr(resp, "data", []) or []:
                mid = getattr(m, "id", None)
                if isinstance(mid, str) and mid.startswith("claude-"):
                    ids.append(mid)
            ids = sorted(set(ids))
            if ids:
                models = ids
                source = "api"
        except Exception:
            pass

    data = {"models": [{"id": m} for m in models], "source": source}
    _cache_set("claude_models", data)
    return data

