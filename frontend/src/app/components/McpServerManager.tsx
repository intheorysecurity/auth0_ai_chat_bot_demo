"use client";

import { useState } from "react";
import { McpServer } from "@/lib/hooks/useMcpServers";

interface McpServerManagerProps {
  servers: McpServer[];
  onConnect: (url: string) => Promise<{
    status: "connected" | "auth_required" | "error";
    authUrl?: string;
    message?: string;
  }>;
  onDisconnect: (url: string) => Promise<void>;
}

export default function McpServerManager({
  servers,
  onConnect,
  onDisconnect,
}: McpServerManagerProps) {
  const [newUrl, setNewUrl] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [expandedUrl, setExpandedUrl] = useState<string | null>(null);

  const handleConnect = async () => {
    if (!newUrl.trim()) return;
    setConnecting(true);
    setConnectError(null);
    try {
      const result = await onConnect(newUrl.trim());
      if (result.status === "auth_required" && result.authUrl) {
        window.open(result.authUrl, "mcp-auth", "width=600,height=700");
      } else if (result.status === "error") {
        setConnectError(result.message || "Failed to connect.");
      }
      if (result.status === "connected") {
        setNewUrl("");
      }
    } finally {
      setConnecting(false);
    }
  };

  return (
    <div className="p-4 space-y-4">
      <h3 className="text-sm font-medium text-gray-900 dark:text-white">
        MCP Servers
      </h3>

      <div className="space-y-2">
        {servers.map((server) => (
          <div
            key={server.url}
            className="p-2 bg-gray-50 dark:bg-gray-700 rounded-md text-xs space-y-2"
          >
            <div className="flex items-center justify-between gap-2">
              <button
                type="button"
                onClick={() =>
                  setExpandedUrl((prev) => (prev === server.url ? null : server.url))
                }
                className="flex items-center gap-2 min-w-0 text-left"
                title="Toggle tool list"
              >
                <span
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    server.connected ? "bg-green-500" : "bg-gray-400"
                  }`}
                />
                <span className="truncate text-gray-700 dark:text-gray-300">
                  {server.url}
                </span>
                {server.connected && (
                  <span className="text-gray-500">({server.tools_count} tools)</span>
                )}
                <span className="text-gray-400 ml-1">
                  {expandedUrl === server.url ? "^" : "v"}
                </span>
              </button>

              <div className="flex gap-1 flex-shrink-0">
                {server.authRequired && server.authUrl && (
                  <button
                    onClick={() =>
                      window.open(
                        server.authUrl,
                        "mcp-auth",
                        "width=600,height=700"
                      )
                    }
                    className="px-2 py-1 text-xs bg-yellow-100 text-yellow-800 rounded hover:bg-yellow-200"
                  >
                    Authenticate
                  </button>
                )}
                {server.connected && (
                  <button
                    onClick={() => onDisconnect(server.url)}
                    className="px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                  >
                    Disconnect
                  </button>
                )}
              </div>
            </div>

            {expandedUrl === server.url && (
              <div className="text-[11px] text-gray-600 dark:text-gray-300">
                {!server.connected ? (
                  <div>Not connected.</div>
                ) : server.tools && server.tools.length > 0 ? (
                  <div className="space-y-1">
                    <div className="text-gray-500">Tools:</div>
                    <ul className="list-disc pl-4 space-y-0.5">
                      {server.tools.slice(0, 15).map((t) => (
                        <li key={t.name}>
                          <span className="font-mono">{t.name}</span>
                          {t.description ? (
                            <span className="text-gray-500"> — {t.description}</span>
                          ) : null}
                        </li>
                      ))}
                      {server.tools.length > 15 ? (
                        <li className="text-gray-500">
                          …and {server.tools.length - 15} more
                        </li>
                      ) : null}
                    </ul>
                  </div>
                ) : (
                  <div className="text-gray-500">
                    Connected, but the server reported no tools.
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={newUrl}
          onChange={(e) => setNewUrl(e.target.value)}
          placeholder="MCP server URL..."
          className="flex-1 text-xs px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={handleConnect}
          disabled={connecting || !newUrl.trim()}
          className="px-3 py-2 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {connecting ? "..." : "Connect"}
        </button>
      </div>

      {connectError ? (
        <div className="text-xs text-red-600 dark:text-red-400 whitespace-pre-wrap">
          {connectError}
        </div>
      ) : null}
    </div>
  );
}
