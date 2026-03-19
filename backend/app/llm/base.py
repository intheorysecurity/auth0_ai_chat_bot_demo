from abc import ABC, abstractmethod
from typing import AsyncIterator

from pydantic import BaseModel


class TextDelta(BaseModel):
    type: str = "text_delta"
    text: str


class ToolCallRequest(BaseModel):
    type: str = "tool_call"
    tool_call_id: str
    tool_name: str
    arguments: dict


class Done(BaseModel):
    type: str = "done"
    usage: dict | None = None


StreamChunk = TextDelta | ToolCallRequest | Done


class LLMProvider(ABC):
    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Yield StreamChunk items for a chat completion.

        If the LLM requests a tool call, yield a ToolCallRequest.
        The caller is responsible for executing the tool and re-invoking
        with the result appended to messages.
        """
        ...
