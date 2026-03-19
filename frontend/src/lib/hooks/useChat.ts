"use client";

import { useCallback, useState } from "react";
import { getAuthedJson, streamChat } from "@/lib/api";
import { fetchOrdersListMarkdown } from "@/lib/ordersListShortcut";
import {
  stripAssistantArtifacts,
  userWantsOrdersListOnly,
} from "@/lib/stripAssistantArtifacts";

export interface ToolCallInfo {
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  result?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  toolCalls?: ToolCallInfo[];
  isStreaming?: boolean;
}

export function useChat(accessToken?: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [model, setModel] = useState("claude");
  const [modelId, setModelId] = useState<string | undefined>();
  const [mcpServerUrls, setMcpServerUrls] = useState<string[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();

  const loadConversation = useCallback(
    (
      nextConversationId: string | undefined,
      apiMessages: { role: "user" | "assistant" | "system"; content: string }[]
    ) => {
      setConversationId(nextConversationId);
      setMessages(
        apiMessages.map((m) => ({
          id: crypto.randomUUID(),
          role: m.role,
          content: m.content,
          isStreaming: false,
        }))
      );
    },
    []
  );

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      const normalized = content
        .trim()
        .toLowerCase()
        .replace(/[?.!]+$/g, "");

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content,
      };

      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
        toolCalls: [],
        isStreaming: true,
      };

      // Local "whoami" shortcut: show authenticated user claims.
      if (normalized === "whoami" || normalized === "who am i") {
        setMessages((prev) => [
          ...prev,
          userMessage,
          { ...assistantMessage, isStreaming: false },
        ]);
        setIsLoading(true);
        try {
          if (!accessToken) {
            throw new Error("Not authenticated (missing access token on client).");
          }
          const data = await getAuthedJson<{ user: Record<string, unknown> }>(
            "/api/auth/me",
            accessToken
          );

          const user = data.user || {};
          const lines: string[] = [];
          if (typeof user["name"] === "string" && user["name"]) {
            lines.push(`Name: ${user["name"]}`);
          }
          if (typeof user["email"] === "string" && user["email"]) {
            lines.push(`Email: ${user["email"]}`);
          }
          if (typeof user["sub"] === "string" && user["sub"]) {
            lines.push(`Subject: ${user["sub"]}`);
          }
          if (typeof user["iss"] === "string" && user["iss"]) {
            lines.push(`Issuer: ${user["iss"]}`);
          }
          if (typeof user["aud"] === "string" && user["aud"]) {
            lines.push(`Audience: ${user["aud"]}`);
          }

          const response =
            lines.length > 0
              ? `Authenticated as:\n${lines.map((l) => `- ${l}`).join("\n")}`
              : `Authenticated, but no standard claims were returned.\n\n${JSON.stringify(
                  user,
                  null,
                  2
                )}`;

          setMessages((prev) => {
            const updated = prev.slice();
            const lastIdx = updated.length - 1;
            const last = updated[lastIdx];
            if (last && last.role === "assistant") {
              updated[lastIdx] = { ...last, content: response };
            }
            return updated;
          });
        } catch (e) {
          const msg = e instanceof Error ? e.message : "Unknown error";
          setMessages((prev) => {
            const updated = prev.slice();
            const lastIdx = updated.length - 1;
            const last = updated[lastIdx];
            if (last && last.role === "assistant") {
              updated[lastIdx] = { ...last, content: `[Error: ${msg}]` };
            }
            return updated;
          });
        } finally {
          setIsLoading(false);
        }
        return;
      }

      // Local orders shortcut: same data as list_orders tool, stable markdown (no model thinking leak).
      if (userWantsOrdersListOnly(content)) {
        setMessages((prev) => [
          ...prev,
          userMessage,
          { ...assistantMessage, isStreaming: false },
        ]);
        setIsLoading(true);
        try {
          if (!accessToken) {
            throw new Error("Not authenticated (missing access token on client).");
          }
          const response = await fetchOrdersListMarkdown(accessToken);
          setMessages((prev) => {
            const updated = prev.slice();
            const lastIdx = updated.length - 1;
            const last = updated[lastIdx];
            if (last && last.role === "assistant") {
              updated[lastIdx] = { ...last, content: response };
            }
            return updated;
          });
        } catch (e) {
          const msg = e instanceof Error ? e.message : "Unknown error";
          setMessages((prev) => {
            const updated = prev.slice();
            const lastIdx = updated.length - 1;
            const last = updated[lastIdx];
            if (last && last.role === "assistant") {
              updated[lastIdx] = { ...last, content: `[Error loading orders: ${msg}]` };
            }
            return updated;
          });
        } finally {
          setIsLoading(false);
        }
        return;
      }

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsLoading(true);

      const apiMessages = [...messages, userMessage].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      try {
        await streamChat(
          {
            messages: apiMessages,
            model,
            model_id: modelId,
            mcp_server_urls: mcpServerUrls,
            conversation_id: conversationId,
          },
          {
            onConversation: (data) => {
              if (data?.conversation_id) {
                setConversationId(data.conversation_id);
              }
            },
            onTextDelta: (text) => {
              setMessages((prev) => {
                const updated = prev.slice();
                const lastIdx = updated.length - 1;
                const last = updated[lastIdx];
                if (last && last.role === "assistant") {
                  updated[lastIdx] = { ...last, content: last.content + text };
                }
                return updated;
              });
            },
            onToolCall: (data) => {
              setMessages((prev) => {
                const updated = prev.slice();
                const lastIdx = updated.length - 1;
                const last = updated[lastIdx];
                if (last && last.role === "assistant") {
                  updated[lastIdx] = {
                    ...last,
                    toolCalls: [
                      ...(last.toolCalls || []),
                      {
                        tool_call_id: data.tool_call_id,
                        tool_name: data.tool_name,
                        arguments: data.arguments,
                      },
                    ],
                  };
                }
                return updated;
              });
            },
            onToolResult: (data) => {
              setMessages((prev) => {
                const updated = prev.slice();
                const lastIdx = updated.length - 1;
                const last = updated[lastIdx];
                if (last && last.role === "assistant" && last.toolCalls?.length) {
                  const tcIdx = last.toolCalls.findIndex(
                    (t) => t.tool_call_id === data.tool_call_id
                  );
                  if (tcIdx >= 0) {
                    const nextToolCalls = last.toolCalls.slice();
                    nextToolCalls[tcIdx] = {
                      ...nextToolCalls[tcIdx],
                      result: data.result,
                    };
                    updated[lastIdx] = { ...last, toolCalls: nextToolCalls };
                  }
                }
                return updated;
              });
            },
            onDone: () => {
              setMessages((prev) => {
                const updated = prev.slice();
                const lastIdx = updated.length - 1;
                const last = updated[lastIdx];
                if (last && last.role === "assistant") {
                  updated[lastIdx] = {
                    ...last,
                    content: stripAssistantArtifacts(last.content),
                    isStreaming: false,
                  };
                }
                return updated;
              });
            },
            onError: (message) => {
              setMessages((prev) => {
                const updated = prev.slice();
                const lastIdx = updated.length - 1;
                const last = updated[lastIdx];
                if (last && last.role === "assistant") {
                  updated[lastIdx] = {
                    ...last,
                    content: last.content + `\n\n[Error: ${message}]`,
                    isStreaming: false,
                  };
                }
                return updated;
              });
            },
          },
          accessToken
        );
      } finally {
        setIsLoading(false);
      }
    },
    [messages, model, modelId, mcpServerUrls, accessToken, isLoading, conversationId]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setConversationId(undefined);
  }, []);

  return {
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
  };
}
