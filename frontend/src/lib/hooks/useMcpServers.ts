"use client";

import { useCallback, useState } from "react";
import { apiJson } from "@/lib/api";

export interface McpServer {
  url: string;
  connected: boolean;
  tools_count: number;
  tools?: { name: string; description: string }[];
  authRequired?: boolean;
  authUrl?: string;
}

export function useMcpServers(accessToken?: string) {
  const [servers, setServers] = useState<McpServer[]>([]);

  const headers: Record<string, string> = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const refreshServers = useCallback(async () => {
    try {
      const data = await apiJson<{ servers: McpServer[] }>("/api/mcp/servers", {
        headers,
      });
      setServers(data.servers);
    } catch {
      // silently fail - servers may not be configured
    }
  }, [accessToken]);

  const connectServer = useCallback(
    async (url: string) => {
      try {
        const data = await apiJson<{
          status: string;
          tools?: { name: string; description: string }[];
          auth_url?: string;
          message?: string;
        }>("/api/mcp/connect", {
          method: "POST",
          headers,
          body: JSON.stringify({ url }),
        });

        if (data.status === "connected") {
          setServers((prev) => [
            ...prev.filter((s) => s.url !== url),
            {
              url,
              connected: true,
              tools_count: data.tools?.length || 0,
              tools: data.tools,
            },
          ]);
          return { status: "connected" as const };
        } else if (data.status === "auth_required") {
          setServers((prev) => [
            ...prev.filter((s) => s.url !== url),
            {
              url,
              connected: false,
              tools_count: 0,
              authRequired: true,
              authUrl: data.auth_url,
            },
          ]);
          return { status: "auth_required" as const, authUrl: data.auth_url };
        } else {
          return { status: "error" as const, message: data.message };
        }
      } catch (e) {
        return {
          status: "error" as const,
          message: e instanceof Error ? e.message : "Unknown error",
        };
      }
    },
    [accessToken]
  );

  const disconnectServer = useCallback(
    async (url: string) => {
      await apiJson("/api/mcp/disconnect", {
        method: "POST",
        headers,
        body: JSON.stringify({ url }),
      });
      setServers((prev) => prev.filter((s) => s.url !== url));
    },
    [accessToken]
  );

  return {
    servers,
    refreshServers,
    connectServer,
    disconnectServer,
  };
}
