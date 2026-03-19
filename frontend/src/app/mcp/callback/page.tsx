"use client";

import { getAccessToken } from "@auth0/nextjs-auth0";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiJson } from "@/lib/api";

function McpCallbackContent() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"processing" | "success" | "error">(
    "processing"
  );
  const [message, setMessage] = useState("");

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (!code || !state) {
      setStatus("error");
      setMessage("Missing code or state parameter");
      return;
    }

    (async () => {
      try {
        const accessToken = await getAccessToken();
        const data = await apiJson<{
          status: string;
          message?: string;
          server_url?: string;
        }>("/api/mcp/oauth/callback", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({ code, state }),
        });

        if (data.status === "connected") {
          setStatus("success");
          setMessage("MCP server authenticated successfully!");
          if (window.opener && data.server_url) {
            window.opener.postMessage(
              { type: "mcp_oauth_complete", serverUrl: data.server_url },
              window.location.origin
            );
          }
          setTimeout(() => {
            window.close();
          }, 2000);
        } else {
          setStatus("error");
          setMessage(data.message || "Authentication failed");
        }
      } catch (e) {
        setStatus("error");
        setMessage(e instanceof Error ? e.message : "Authentication failed");
      }
    })();
  }, [searchParams]);

  return (
    <div className="text-center space-y-4 max-w-sm">
      {status === "processing" && (
        <>
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
          <p className="text-gray-600 dark:text-gray-400">
            Completing authentication...
          </p>
        </>
      )}
      {status === "success" && (
        <>
          <div className="text-green-600 text-4xl">&#10003;</div>
          <p className="text-gray-900 dark:text-white font-medium">{message}</p>
          <p className="text-sm text-gray-500">
            This window will close automatically.
          </p>
        </>
      )}
      {status === "error" && (
        <>
          <div className="text-red-600 text-4xl">&#10007;</div>
          <p className="text-gray-900 dark:text-white font-medium">
            Authentication Failed
          </p>
          <p className="text-sm text-red-600">{message}</p>
          <button
            onClick={() => window.close()}
            className="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded-md text-sm"
          >
            Close
          </button>
        </>
      )}
    </div>
  );
}

export default function McpCallbackPage() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900">
      <Suspense
        fallback={
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        }
      >
        <McpCallbackContent />
      </Suspense>
    </div>
  );
}
