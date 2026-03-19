const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  return res;
}

export async function apiJson<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await apiFetch(path, options);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getAuthedJson<T>(
  path: string,
  accessToken: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await apiFetch(path, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${accessToken}`,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export interface SSECallbacks {
  onConversation?: (data: { conversation_id: string }) => void;
  onTextDelta?: (text: string) => void;
  onToolCall?: (data: {
    tool_call_id: string;
    tool_name: string;
    arguments: Record<string, unknown>;
  }) => void;
  onToolResult?: (data: {
    tool_call_id: string;
    result: string;
  }) => void;
  onDone?: (data: { usage: Record<string, unknown> | null }) => void;
  onError?: (message: string) => void;
}

export async function streamChat(
  body: {
    messages: { role: string; content: string }[];
    model: string;
    model_id?: string;
    mcp_server_urls?: string[];
    conversation_id?: string;
  },
  callbacks: SSECallbacks,
  accessToken?: string
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const res = await fetch(`${API_URL}/api/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text();
    callbacks.onError?.(text || `HTTP ${res.status}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let currentEvent = "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ") && currentEvent) {
        const data = JSON.parse(line.slice(6));
        switch (currentEvent) {
          case "conversation":
            callbacks.onConversation?.(data);
            break;
          case "text_delta":
            callbacks.onTextDelta?.(data.text);
            break;
          case "tool_call":
            callbacks.onToolCall?.(data);
            break;
          case "tool_result":
            callbacks.onToolResult?.(data);
            break;
          case "done":
            callbacks.onDone?.(data);
            break;
          case "error":
            callbacks.onError?.(data.message);
            break;
        }
        currentEvent = "";
      }
    }
  }
}
