import json
from typing import AsyncIterator

import openai

from app.config import settings
from app.llm.base import Done, LLMProvider, StreamChunk, TextDelta, ToolCallRequest


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        model = model or "gpt-4o"

        # Convert tool definitions to OpenAI format
        openai_tools = None
        if tools:
            openai_tools = [
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

        kwargs: dict = {
            "model": model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        tool_calls_accum: dict[int, dict] = {}

        async for chunk in await self._client.chat.completions.create(**kwargs):
            choice = chunk.choices[0] if chunk.choices else None

            if choice and choice.delta:
                delta = choice.delta

                if delta.content:
                    yield TextDelta(text=delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_accum:
                            tool_calls_accum[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name or "" if tc.function else "",
                                "arguments": "",
                            }
                        if tc.id:
                            tool_calls_accum[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_accum[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_accum[idx]["arguments"] += tc.function.arguments

                if choice.finish_reason == "tool_calls":
                    for tc_data in tool_calls_accum.values():
                        try:
                            arguments = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                        except json.JSONDecodeError:
                            arguments = {}
                        yield ToolCallRequest(
                            tool_call_id=tc_data["id"],
                            tool_name=tc_data["name"],
                            arguments=arguments,
                        )
                    tool_calls_accum.clear()

            if chunk.usage:
                yield Done(
                    usage={
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }
                )
