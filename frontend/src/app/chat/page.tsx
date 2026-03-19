"use client";

import { getAccessToken, useUser } from "@auth0/nextjs-auth0";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useChat } from "@/lib/hooks/useChat";
import { useMcpServers } from "@/lib/hooks/useMcpServers";
import Sidebar from "@/app/components/Sidebar";
import ChatWindow from "@/app/components/ChatWindow";
import ChatInput from "@/app/components/ChatInput";
import { getAuthedJson } from "@/lib/api";

export default function ChatPage() {
  const { user, isLoading: authLoading } = useUser();
  const router = useRouter();

  const [accessToken, setAccessToken] = useState<string | undefined>();
  const [tokenLoading, setTokenLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadToken() {
      if (authLoading) return;
      if (!user) {
        setTokenLoading(false);
        return;
      }

      try {
        const token = await getAccessToken();
        if (!cancelled) setAccessToken(token);
      } catch {
        if (!cancelled) setAccessToken(undefined);
      } finally {
        if (!cancelled) setTokenLoading(false);
      }
    }

    loadToken();
    return () => {
      cancelled = true;
    };
  }, [authLoading, user]);

  const {
    messages,
    isLoading,
    sendMessage,
    clearMessages,
    model,
    setModel,
    modelId,
    setModelId,
    mcpServerUrls,
    setMcpServerUrls,
    conversationId,
    setConversationId,
    loadConversation,
  } = useChat(accessToken);

  const [ollamaModels, setOllamaModels] = useState<
    { name: string; supports_tools: boolean }[]
  >([]);
  const [openaiModels, setOpenaiModels] = useState<{ id: string }[]>([]);
  const [claudeModels, setClaudeModels] = useState<{ id: string }[]>([]);

  const [conversations, setConversations] = useState<
    {
      id: string;
      created_at: number;
      title?: string | null;
      model?: string | null;
      model_id?: string | null;
    }[]
  >([]);

  useEffect(() => {
    async function loadConversations() {
      if (!accessToken) return;
      try {
        const data = await getAuthedJson<{
          conversations: {
            id: string;
            created_at: number;
            title?: string | null;
            model?: string | null;
            model_id?: string | null;
          }[];
        }>("/api/conversations", accessToken);
        setConversations(data.conversations || []);
      } catch {
        // ignore
      }
    }
    loadConversations();
  }, [accessToken]);

  // When Ollama is selected, fetch installed models (and whether they support tools).
  useEffect(() => {
    if (!accessToken) return;
    if (model !== "ollama") return;
    let cancelled = false;
    (async () => {
      try {
        const data = await getAuthedJson<{
          models: { name: string; supports_tools: boolean }[];
        }>("/api/llm/ollama/models", accessToken);
        if (!cancelled) setOllamaModels(data.models || []);
      } catch {
        if (!cancelled) setOllamaModels([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, model]);

  useEffect(() => {
    if (!accessToken) return;
    if (model !== "openai") return;
    let cancelled = false;
    (async () => {
      try {
        const data = await getAuthedJson<{
          models: { id: string }[];
        }>("/api/llm/openai/models", accessToken);
        if (!cancelled) setOpenaiModels(data.models || []);
      } catch {
        if (!cancelled) setOpenaiModels([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, model]);

  useEffect(() => {
    if (!accessToken) return;
    if (model !== "claude") return;
    let cancelled = false;
    (async () => {
      try {
        const data = await getAuthedJson<{
          models: { id: string }[];
        }>("/api/llm/claude/models", accessToken);
        if (!cancelled) setClaudeModels(data.models || []);
      } catch {
        if (!cancelled) setClaudeModels([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, model]);

  const refreshConversations = useCallback(async () => {
    if (!accessToken) return;
    try {
      const data = await getAuthedJson<{
        conversations: {
          id: string;
          created_at: number;
          title?: string | null;
          model?: string | null;
          model_id?: string | null;
        }[];
      }>("/api/conversations", accessToken);
      setConversations(data.conversations || []);
    } catch {
      // ignore
    }
  }, [accessToken]);

  // When the stream assigns a new conversationId, make it appear in the sidebar immediately.
  useEffect(() => {
    if (!accessToken || !conversationId) return;
    const exists = conversations.some((c) => c.id === conversationId);
    if (!exists) {
      refreshConversations();
    }
  }, [accessToken, conversationId, conversations, refreshConversations]);

  const [deletingConversationId, setDeletingConversationId] = useState<
    string | undefined
  >();

  const selectConversation = async (id: string) => {
    if (!accessToken) return;
    try {
      const data = await getAuthedJson<{
        conversation: {
          model?: string | null;
          model_id?: string | null;
          messages: { role: "user" | "assistant" | "system"; content: string }[];
        };
      }>(`/api/conversations/${id}`, accessToken);
      const msgs = data.conversation?.messages || [];
      loadConversation(id, msgs);
      setConversationId(id);
      if (data.conversation?.model) setModel(String(data.conversation.model));
      setModelId(data.conversation?.model_id ? String(data.conversation.model_id) : undefined);
    } catch {
      // ignore
    }
  };

  const deleteConversation = async (id: string) => {
    if (!accessToken) return;
    const ok = window.confirm("Delete this conversation? This cannot be undone.");
    if (!ok) return;
    setDeletingConversationId(id);
    try {
      await getAuthedJson(`/api/conversations/${id}`, accessToken, {
        method: "DELETE",
      });
      if (conversationId === id) {
        clearMessages();
      }
      await refreshConversations();
    } finally {
      setDeletingConversationId(undefined);
    }
  };

  const startNewConversation = async () => {
    clearMessages();
    if (!accessToken) return;
    try {
      const data = await getAuthedJson<{ conversation_id: string }>(
        "/api/conversations",
        accessToken,
        {
          method: "POST",
          body: JSON.stringify({
            model,
            model_id: modelId,
          }),
        }
      );
      setConversationId(data.conversation_id);
      await refreshConversations();
    } catch {
      // ignore
    }
  };

  const { servers, connectServer, disconnectServer, refreshServers } =
    useMcpServers(accessToken);

  useEffect(() => {
    if (accessToken) {
      refreshServers();
    }
  }, [accessToken, refreshServers]);

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      const data = event.data as { type?: string; serverUrl?: string };
      if (data?.type === "mcp_oauth_complete" && data.serverUrl) {
        connectServer(data.serverUrl);
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [connectServer]);

  // Update MCP server URLs when servers change
  useEffect(() => {
    const connectedUrls = servers
      .filter((s) => s.connected)
      .map((s) => s.url);
    setMcpServerUrls(connectedUrls);
  }, [servers, setMcpServerUrls]);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/");
    }
  }, [user, authLoading, router]);

  if (authLoading || tokenLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex h-screen bg-white dark:bg-gray-900">
      <Sidebar
        model={model}
        onModelChange={(next) => {
          setModel(next);
          setModelId(undefined);
        }}
        modelId={modelId}
        onModelIdChange={setModelId}
        ollamaModels={ollamaModels}
        openaiModels={openaiModels}
        claudeModels={claudeModels}
        mcpServers={servers}
        conversations={conversations}
        activeConversationId={conversationId}
        onSelectConversation={selectConversation}
        onDeleteConversation={deleteConversation}
        deletingConversationId={deletingConversationId}
        onMcpConnect={connectServer}
        onMcpDisconnect={disconnectServer}
        onNewChat={startNewConversation}
        onLogout={() => {
          window.location.href = "/auth/logout";
        }}
        userName={user.name || user.email || undefined}
      />
      <div className="flex-1 flex flex-col">
        {!accessToken ? (
          <div className="p-6 text-sm text-gray-700 dark:text-gray-200">
            Could not retrieve an access token. Please log out and log back in.
          </div>
        ) : null}
        <ChatWindow messages={messages} />
        <ChatInput onSend={sendMessage} disabled={isLoading || !accessToken} />
      </div>
    </div>
  );
}
