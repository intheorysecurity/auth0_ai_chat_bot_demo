import json
from typing import AsyncIterator

import anthropic

from app.config import settings
from app.llm.base import Done, LLMProvider, StreamChunk, TextDelta, ToolCallRequest


class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        model = model or "claude-sonnet-4-20250514"

        # Convert tool definitions to Anthropic format
        anthropic_tools = None
        if tools:
            anthropic_tools = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("input_schema", {"type": "object"}),
                }
                for t in tools
            ]

        # Separate system message if present
        system = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append(msg)

        kwargs: dict = {
            "model": model,
            "max_tokens": 4096,
            "messages": chat_messages,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        async with self._client.messages.stream(**kwargs) as stream:
            current_tool_id = None
            current_tool_name = None
            tool_input_json = ""

            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        current_tool_id = event.content_block.id
                        current_tool_name = event.content_block.name
                        tool_input_json = ""

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield TextDelta(text=event.delta.text)
                    elif event.delta.type == "input_json_delta":
                        tool_input_json += event.delta.partial_json

                elif event.type == "content_block_stop":
                    if current_tool_id and current_tool_name:
                        try:
                            arguments = json.loads(tool_input_json) if tool_input_json else {}
                        except json.JSONDecodeError:
                            arguments = {}
                        yield ToolCallRequest(
                            tool_call_id=current_tool_id,
                            tool_name=current_tool_name,
                            arguments=arguments,
                        )
                        current_tool_id = None
                        current_tool_name = None
                        tool_input_json = ""

            # Get final message for usage
            final = await stream.get_final_message()
            yield Done(
                usage={
                    "input_tokens": final.usage.input_tokens,
                    "output_tokens": final.usage.output_tokens,
                }
            )
