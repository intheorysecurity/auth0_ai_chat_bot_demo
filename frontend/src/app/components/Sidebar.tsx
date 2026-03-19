"use client";

import { McpServer } from "@/lib/hooks/useMcpServers";
import Link from "next/link";
import McpServerManager from "./McpServerManager";
import ModelSelector from "./ModelSelector";

interface SidebarProps {
  model: string;
  onModelChange: (model: string) => void;
  modelId?: string;
  onModelIdChange: (modelId: string | undefined) => void;
  ollamaModels?: { name: string; supports_tools: boolean }[];
  openaiModels?: { id: string }[];
  claudeModels?: { id: string }[];
  mcpServers: McpServer[];
  conversations: {
    id: string;
    created_at: number;
    title?: string | null;
    model?: string | null;
    model_id?: string | null;
  }[];
  activeConversationId?: string;
  onSelectConversation: (conversationId: string) => void;
  onDeleteConversation: (conversationId: string) => void;
  deletingConversationId?: string;
  onMcpConnect: (url: string) => Promise<{
    status: "connected" | "auth_required" | "error";
    authUrl?: string;
    message?: string;
  }>;
  onMcpDisconnect: (url: string) => Promise<void>;
  onNewChat: () => void;
  onLogout: () => void;
  userName?: string;
}

export default function Sidebar({
  model,
  onModelChange,
  modelId,
  onModelIdChange,
  ollamaModels,
  openaiModels,
  claudeModels,
  mcpServers,
  conversations,
  activeConversationId,
  onSelectConversation,
  onDeleteConversation,
  deletingConversationId,
  onMcpConnect,
  onMcpDisconnect,
  onNewChat,
  onLogout,
  userName,
}: SidebarProps) {
  return (
    <div className="w-72 bg-gray-50 dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          AI Chat Bot
        </h2>
        {userName && (
          <p className="text-xs text-gray-500 mt-1 truncate">{userName}</p>
        )}
      </div>

      {/* Model Selection */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <label className="text-xs font-medium text-gray-500 dark:text-gray-400 block mb-2">
          Model
        </label>
        <ModelSelector model={model} onModelChange={onModelChange} />
        {model === "ollama" ? (
          <div className="mt-3">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 block mb-2">
              Ollama model
            </label>
            <select
              value={modelId || ""}
              onChange={(e) => onModelIdChange(e.target.value || undefined)}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Auto (pick default)</option>
              {(ollamaModels || []).map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                  {m.supports_tools ? " (tools)" : ""}
                </option>
              ))}
            </select>
            <input
              value={modelId || ""}
              onChange={(e) => onModelIdChange(e.target.value || undefined)}
              placeholder="Or type a model id (optional)"
              className="mt-2 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {ollamaModels && ollamaModels.length === 0 ? (
              <div className="mt-2 text-[11px] text-gray-500 dark:text-gray-400">
                No Ollama models found. Run `ollama pull &lt;model&gt;` first.
              </div>
            ) : null}
          </div>
        ) : null}
        {model === "openai" ? (
          <div className="mt-3">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 block mb-2">
              OpenAI model
            </label>
            <select
              value={modelId || ""}
              onChange={(e) => onModelIdChange(e.target.value || undefined)}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Default (gpt-4o)</option>
              {(openaiModels || []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.id}
                </option>
              ))}
            </select>
            <input
              value={modelId || ""}
              onChange={(e) => onModelIdChange(e.target.value || undefined)}
              placeholder="Or type a model id (optional)"
              className="mt-2 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        ) : null}
        {model === "claude" ? (
          <div className="mt-3">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 block mb-2">
              Claude model
            </label>
            <select
              value={modelId || ""}
              onChange={(e) => onModelIdChange(e.target.value || undefined)}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Default (sonnet)</option>
              {(claudeModels || []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.id}
                </option>
              ))}
            </select>
            <input
              value={modelId || ""}
              onChange={(e) => onModelIdChange(e.target.value || undefined)}
              placeholder="Or type a model id (optional)"
              className="mt-2 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        ) : null}
      </div>

      {/* New Chat */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={onNewChat}
          className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-gray-700 dark:text-gray-300"
        >
          + New Chat
        </button>
      </div>

      {/* Conversations */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <div className="px-4 pt-4 pb-2">
          <div className="text-xs font-medium text-gray-500 dark:text-gray-400">
            Chats
          </div>
        </div>
        <div className="px-2 pb-3 max-h-56 overflow-y-auto">
          {conversations.length === 0 ? (
            <div className="px-2 py-2 text-xs text-gray-500 dark:text-gray-400">
              No saved chats yet.
            </div>
          ) : (
            <div className="space-y-1">
              {conversations.map((c) => {
                const isActive = c.id === activeConversationId;
                const label = c.title || c.id.slice(0, 12);
                const meta = c.model
                  ? `${c.model}${c.model_id ? `:${c.model_id}` : ""}`
                  : undefined;
                const isDeleting = deletingConversationId === c.id;
                return (
                  <div
                    key={c.id}
                    className={`w-full text-left px-3 py-2 rounded-md border text-xs transition-colors ${
                      isActive
                        ? "bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600"
                        : "bg-transparent border-transparent hover:bg-gray-100 dark:hover:bg-gray-700"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <button
                          type="button"
                          onClick={() => onSelectConversation(c.id)}
                          className="block w-full text-left"
                        >
                          <div className="truncate text-gray-900 dark:text-gray-100">
                            {label}
                          </div>
                          {meta ? (
                            <div className="truncate text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
                              {meta}
                            </div>
                          ) : null}
                        </button>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          onDeleteConversation(c.id);
                        }}
                        disabled={isDeleting}
                        className="px-2 py-1 text-[11px] border border-red-200 dark:border-red-800 rounded text-red-700 dark:text-red-200 hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50"
                        title="Delete chat"
                      >
                        {isDeleting ? "…" : "Del"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* MCP Servers */}
      <div className="flex-1 overflow-y-auto border-b border-gray-200 dark:border-gray-700">
        <McpServerManager
          servers={mcpServers}
          onConnect={onMcpConnect}
          onDisconnect={onMcpDisconnect}
        />
      </div>

      {/* Logout */}
      <div className="p-4">
        <Link
          href="/profile"
          className="mb-3 block w-full text-center px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-gray-700 dark:text-gray-300"
        >
          Profile
        </Link>
        <button
          onClick={onLogout}
          className="w-full px-3 py-2 text-sm text-red-600 border border-red-200 dark:border-red-800 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
        >
          Sign Out
        </button>
      </div>
    </div>
  );
}
