from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_call_id: str | None = None
    tool_name: str | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "claude"  # "claude", "openai", "ollama"
    model_id: str | None = None  # specific model ID, e.g. "gpt-4o-mini"
    mcp_server_urls: list[str] = []
    conversation_id: str | None = None
