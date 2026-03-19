import json
import uuid
from typing import AsyncIterator

import httpx

from app.config import settings
from app.llm.base import Done, LLMProvider, StreamChunk, TextDelta, ToolCallRequest


class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")

    async def _get_available_models(self, client: httpx.AsyncClient) -> list[dict]:
        try:
            resp = await client.get(f"{self._base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])
            return models if isinstance(models, list) else []
        except Exception:
            return []

    def _pick_default_model(self, models: list[dict]) -> str | None:
        # Prefer a local/non-cloud model when available.
        for m in models:
            name = m.get("name") or m.get("model")
            if not name:
                continue
            if not m.get("remote_host") and not str(name).endswith("-cloud"):
                return str(name)

        for m in models:
            name = m.get("name") or m.get("model")
            if name:
                return str(name)
        return None

    def _format_model_not_found(self, requested: str, models: list[dict]) -> str:
        names: list[str] = []
        for m in models:
            name = m.get("name") or m.get("model")
            if isinstance(name, str):
                names.append(name)
        names = sorted(set(names))
        suffix = ""
        if names:
            suffix = "\nAvailable models:\n- " + "\n- ".join(names[:25])
            if len(names) > 25:
                suffix += f"\n- ...and {len(names) - 25} more"
        return (
            f"Ollama model '{requested}' not found. "
            f"Either set `model_id` to an installed model, or run `ollama pull {requested}`."
            f"{suffix}"
        )

    def _messages_to_prompt(self, messages: list[dict]) -> str:
        # Best-effort conversion for /api/generate fallback.
        lines: list[str] = []
        for m in messages:
            role = str(m.get("role", "user"))
            content = str(m.get("content", ""))
            if not content:
                continue
            if role == "system":
                lines.append(f"System: {content}")
            elif role == "assistant":
                lines.append(f"Assistant: {content}")
            else:
                lines.append(f"User: {content}")
        lines.append("Assistant:")
        return "\n".join(lines).strip()

    async def _stream_chat_api(
        self, client: httpx.AsyncClient, payload: dict
    ) -> AsyncIterator[StreamChunk]:
        async with client.stream(
            "POST",
            f"{self._base_url}/api/chat",
            json=payload,
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                data = json.loads(line)

                msg = data.get("message", {})
                if msg.get("tool_calls"):
                    # Ollama may send tool_calls on multiple stream lines; each line often
                    # uses index 0 — do not use enumerate index alone (duplicate ids break UI + result routing).
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        tid = tc.get("id")
                        tool_call_id = (
                            str(tid).strip()
                            if isinstance(tid, str) and str(tid).strip()
                            else f"ollama_{uuid.uuid4().hex}"
                        )
                        yield ToolCallRequest(
                            tool_call_id=tool_call_id,
                            tool_name=fn.get("name", ""),
                            arguments=fn.get("arguments", {}),
                        )
                elif msg.get("content"):
                    yield TextDelta(text=msg["content"])

                if data.get("done"):
                    yield Done(
                        usage={
                            "total_duration": data.get("total_duration"),
                            "eval_count": data.get("eval_count"),
                        }
                    )

    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        # Convert tool definitions to Ollama format (only for /api/chat).
        ollama_tools = None
        if tools:
            ollama_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {"type": "object"}),
                    },
                }
                for t in tools
            ]

        async with httpx.AsyncClient(timeout=120.0) as client:
            available_models: list[dict] = []
            if model is None:
                if settings.ollama_default_model:
                    model = settings.ollama_default_model
                else:
                    available_models = await self._get_available_models(client)
                    picked = self._pick_default_model(available_models)
                    if not picked:
                        raise ValueError(
                            "No Ollama models found. Run `ollama pull <model>` first "
                            "(e.g. `ollama pull llama3.2`) or set `model_id` to an installed model."
                        )
                    model = picked

            # Prefer /api/chat. If the Ollama server is older (or behind a proxy) and doesn't
            # expose /api/chat, fall back to /api/generate.
            try:
                chat_payload_base: dict = {
                    "model": model,
                    "messages": messages,
                    "stream": True,
                }
                chat_payload_with_tools = (
                    {**chat_payload_base, "tools": ollama_tools} if ollama_tools else None
                )

                if chat_payload_with_tools:
                    async with client.stream(
                        "POST",
                        f"{self._base_url}/api/chat",
                        json=chat_payload_with_tools,
                    ) as response:
                        if response.status_code == 404:
                            body = await response.aread()
                            # If the endpoint exists but the model doesn't, don't fall back.
                            try:
                                err = json.loads(body.decode("utf-8")).get("error", "")
                            except Exception:
                                err = ""
                            if "model" in str(err).lower() and "not found" in str(err).lower():
                                if not available_models:
                                    available_models = await self._get_available_models(client)
                                raise ValueError(
                                    self._format_model_not_found(model, available_models)
                                )
                            # Otherwise treat as missing endpoint and try /api/generate.
                            raise httpx.HTTPStatusError(
                                "Ollama /api/chat not found",
                                request=response.request,
                                response=response,
                            )

                        if response.status_code == 400:
                            body = await response.aread()
                            try:
                                err = json.loads(body.decode("utf-8")).get("error", "")
                            except Exception:
                                err = body.decode("utf-8", errors="replace")
                            if "does not support tools" in str(err).lower():
                                # Retry without tools for models that don't support them.
                                async for chunk in self._stream_chat_api(
                                    client, chat_payload_base
                                ):
                                    yield chunk
                                return

                            raise ValueError(f"Ollama /api/chat 400: {err}")

                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue
                            data = json.loads(line)

                            msg = data.get("message", {})
                            if msg.get("tool_calls"):
                                for tc in msg["tool_calls"]:
                                    fn = tc.get("function", {})
                                    tid = tc.get("id")
                                    tool_call_id = (
                                        str(tid).strip()
                                        if isinstance(tid, str) and str(tid).strip()
                                        else f"ollama_{uuid.uuid4().hex}"
                                    )
                                    yield ToolCallRequest(
                                        tool_call_id=tool_call_id,
                                        tool_name=fn.get("name", ""),
                                        arguments=fn.get("arguments", {}),
                                    )
                            elif msg.get("content"):
                                yield TextDelta(text=msg["content"])

                            if data.get("done"):
                                yield Done(
                                    usage={
                                        "total_duration": data.get("total_duration"),
                                        "eval_count": data.get("eval_count"),
                                    }
                                )
                        return

                async for chunk in self._stream_chat_api(client, chat_payload_base):
                    yield chunk
                return
            except httpx.HTTPStatusError as e:
                if e.response is None or e.response.status_code != 404:
                    raise

            # Fallback: /api/generate (no tools support here).
            generate_payload = {
                "model": model,
                "prompt": self._messages_to_prompt(messages),
                "stream": True,
            }

            async with client.stream(
                "POST",
                f"{self._base_url}/api/generate",
                json=generate_payload,
            ) as response:
                if response.status_code == 404:
                    body = await response.aread()
                    try:
                        err = json.loads(body.decode("utf-8")).get("error", "")
                    except Exception:
                        err = ""
                    if "model" in str(err).lower() and "not found" in str(err).lower():
                        if not available_models:
                            available_models = await self._get_available_models(client)
                        raise ValueError(self._format_model_not_found(model, available_models))
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)

                    if data.get("response"):
                        yield TextDelta(text=data["response"])

                    if data.get("done"):
                        yield Done(
                            usage={
                                "total_duration": data.get("total_duration"),
                                "eval_count": data.get("eval_count"),
                            }
                        )
