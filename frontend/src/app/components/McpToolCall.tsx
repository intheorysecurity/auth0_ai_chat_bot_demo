"use client";

import { useEffect, useState } from "react";
import { ToolCallInfo } from "@/lib/hooks/useChat";
import { getAccessToken } from "@auth0/nextjs-auth0";
import { apiJson } from "@/lib/api";
import {
  ProductDetailToolTable,
  ProductListToolTable,
  tryParseGetProductResult,
  tryParseListProductsResult,
} from "./ProductCatalogToolView";

interface McpToolCallProps {
  toolCall: ToolCallInfo;
}

const DEFAULT_CIBA_TIMEOUT_SEC = 60;
const MIN_TIMEOUT_SEC = 30;
const MAX_TIMEOUT_SEC = 120;

function toolResultBadge(text: string | undefined): { label: string; className: string } {
  if (!text) {
    return {
      label: "running...",
      className: "text-yellow-600 dark:text-yellow-400 ml-auto animate-pulse",
    };
  }
  try {
    const p = JSON.parse(text) as { status?: string };
    if (p.status === "approval_required") {
      return {
        label: "awaiting CIBA approval",
        className: "text-amber-600 dark:text-amber-400 ml-auto",
      };
    }
    if (p.status === "pending") {
      return {
        label: "approval pending…",
        className: "text-amber-600 dark:text-amber-400 ml-auto",
      };
    }
    if (p.status === "timeout") {
      return { label: "timed out", className: "text-red-600 dark:text-red-400 ml-auto" };
    }
    if (p.status === "denied") {
      return { label: "approval denied", className: "text-red-600 dark:text-red-400 ml-auto" };
    }
    if (p.status === "error") {
      return { label: "error", className: "text-red-600 dark:text-red-400 ml-auto" };
    }
    if (p.status === "approved") {
      return { label: "completed", className: "text-green-600 dark:text-green-400 ml-auto" };
    }
  } catch {
    // ignore
  }
  return { label: "completed", className: "text-green-600 dark:text-green-400 ml-auto" };
}

export default function McpToolCall({ toolCall }: McpToolCallProps) {
  const [expanded, setExpanded] = useState(false);
  const [localResult, setLocalResult] = useState<string | undefined>();
  const [pinnedAuthReqId, setPinnedAuthReqId] = useState<string | null>(null);

  const resultText = localResult ?? toolCall.result;
  const badge = toolResultBadge(resultText);

  const listProductsPreview =
    toolCall.tool_name === "list_products" && resultText
      ? tryParseListProductsResult(resultText)
      : null;
  const getProductPreview =
    toolCall.tool_name === "get_product" && resultText
      ? tryParseGetProductResult(resultText)
      : null;

  useEffect(() => {
    if (!resultText) return;
    try {
      const p = JSON.parse(resultText) as { status?: string; auth_req_id?: string };
      if (p.status === "approval_required" && p.auth_req_id) {
        setPinnedAuthReqId(String(p.auth_req_id));
      }
      if (
        p.status === "approved" ||
        p.status === "denied" ||
        p.status === "timeout" ||
        p.status === "error"
      ) {
        setPinnedAuthReqId(null);
      }
    } catch {
      /* ignore */
    }
  }, [resultText]);

  /** Auto-poll CIBA after approval_required; abandon checkout after timeout. */
  useEffect(() => {
    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const raw = toolCall.result;
    if (!raw) return;

    let parsed: {
      status?: string;
      auth_req_id?: string;
      poll_interval_sec?: number;
      approval_timeout_sec?: number;
    };
    try {
      parsed = JSON.parse(raw);
    } catch {
      return;
    }
    if (parsed.status !== "approval_required" || !parsed.auth_req_id) return;

    const authReqId = String(parsed.auth_req_id);
    const intervalMs = Math.min(
      Math.max(
        (typeof parsed.poll_interval_sec === "number" ? parsed.poll_interval_sec : 3) * 1000,
        2000
      ),
      15000
    );
    let timeoutSec =
      typeof parsed.approval_timeout_sec === "number"
        ? parsed.approval_timeout_sec
        : DEFAULT_CIBA_TIMEOUT_SEC;
    timeoutSec = Math.min(Math.max(timeoutSec, MIN_TIMEOUT_SEC), MAX_TIMEOUT_SEC);
    const timeoutMs = timeoutSec * 1000;

    setPinnedAuthReqId(authReqId);

    const stopPollingOnly = () => {
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const tick = async () => {
      if (cancelled) return;
      try {
        const token = await getAccessToken();
        const data = await apiJson<Record<string, unknown>>("/api/ciba/poll", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: JSON.stringify({ auth_req_id: authReqId }),
        });
        if (cancelled) return;
        setLocalResult(JSON.stringify(data, null, 2));
        const st = data.status as string | undefined;
        if (st === "approved" || st === "denied") {
          cancelled = true;
          stopPollingOnly();
          if (timeoutId !== null) {
            clearTimeout(timeoutId);
            timeoutId = null;
          }
        } else if (st === "error") {
          cancelled = true;
          stopPollingOnly();
          if (timeoutId !== null) {
            clearTimeout(timeoutId);
            timeoutId = null;
          }
        }
      } catch (e) {
        if (cancelled) return;
        cancelled = true;
        stopPollingOnly();
        if (timeoutId !== null) {
          clearTimeout(timeoutId);
          timeoutId = null;
        }
        setLocalResult(
          JSON.stringify(
            { status: "error", message: e instanceof Error ? e.message : "Unknown error" },
            null,
            2
          )
        );
      }
    };

    timeoutId = setTimeout(async () => {
      if (cancelled) return;
      cancelled = true;
      stopPollingOnly();
      try {
        const token = await getAccessToken();
        await apiJson("/api/ciba/pending/abandon", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: JSON.stringify({ auth_req_id: authReqId }),
        });
      } catch {
        /* ignore */
      }
      setLocalResult(
        JSON.stringify(
          {
            status: "timeout",
            message: `No approval within ${timeoutSec} seconds. Checkout was cancelled.`,
          },
          null,
          2
        )
      );
    }, timeoutMs);

    intervalId = setInterval(tick, intervalMs);
    void tick();

    return () => {
      cancelled = true;
      stopPollingOnly();
      if (timeoutId !== null) clearTimeout(timeoutId);
    };
  }, [toolCall.tool_call_id, toolCall.result]);

  return (
    <div className="border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden text-xs">
      {listProductsPreview ? (
        <div className="px-3 pt-2 pb-1 bg-white dark:bg-gray-800">
          <ProductListToolTable
            products={listProductsPreview.products}
            total_products={listProductsPreview.total_products}
            returned={listProductsPreview.returned}
          />
        </div>
      ) : null}
      {getProductPreview ? (
        <div className="px-3 pt-2 pb-1 bg-white dark:bg-gray-800">
          <ProductDetailToolTable product={getProductPreview} />
        </div>
      ) : null}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-600 hover:bg-gray-100 dark:hover:bg-gray-500 transition-colors text-left"
      >
        <span className="font-mono font-medium text-blue-600 dark:text-blue-400">
          {toolCall.tool_name}
        </span>
        <span className={badge.className}>{badge.label}</span>
        <span className="text-gray-400">{expanded ? "^" : "v"}</span>
      </button>
      {expanded && (
        <div className="p-3 space-y-2 bg-white dark:bg-gray-800">
          <div>
            <div className="font-medium text-gray-500 mb-1">Arguments:</div>
            <pre className="bg-gray-50 dark:bg-gray-900 p-2 rounded overflow-x-auto">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>
          {pinnedAuthReqId && (
            <p className="text-[11px] text-gray-500 dark:text-gray-400">
              Polling CIBA approval automatically. Times out after the server-specified window if there is no
              response.
            </p>
          )}
          {resultText && (
            <div>
              <div className="font-medium text-gray-500 mb-1">Result:</div>
              <pre className="bg-gray-50 dark:bg-gray-900 p-2 rounded overflow-x-auto max-h-48 overflow-y-auto">
                {resultText}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
