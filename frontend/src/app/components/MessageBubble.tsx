"use client";

import { ChatMessage } from "@/lib/hooks/useChat";
import McpToolCall from "./McpToolCall";

interface MessageBubbleProps {
  message: ChatMessage;
}

type ContentPart =
  | { type: "text"; text: string }
  | { type: "image"; url: string; alt?: string };

function parseMessageContent(content: string): ContentPart[] {
  // Supports:
  // - Markdown image syntax: ![alt](https://example.com/image.png)
  // - Direct image URLs: https://example.com/image.png
  const pattern =
    /!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)|\b(https?:\/\/[^\s<>()]+\.(?:png|jpe?g|gif|webp|svg)(?:\?[^\s<>()]*)?)/gi;

  const parts: ContentPart[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(content)) !== null) {
    const start = match.index;
    if (start > lastIndex) {
      parts.push({ type: "text", text: content.slice(lastIndex, start) });
    }

    const alt = match[1];
    const mdUrl = match[2];
    const directUrl = match[3];
    const url = mdUrl || directUrl;
    if (url) {
      parts.push({ type: "image", url, alt: alt || undefined });
    } else {
      // Shouldn't happen, but keep the raw text if it does.
      parts.push({ type: "text", text: match[0] });
    }

    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < content.length) {
    parts.push({ type: "text", text: content.slice(lastIndex) });
  }

  // If there were no matches, keep the original string as a single text part.
  if (parts.length === 0) return [{ type: "text", text: content }];
  return parts;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const parts = parseMessageContent(message.content);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-100"
        }`}
      >
        <div className="text-xs font-medium mb-1 opacity-70">
          {isUser ? "You" : "Assistant"}
        </div>
        <div className="text-sm">
          {parts.map((part, idx) => {
            if (part.type === "text") {
              return (
                <span key={`t-${idx}`} className="whitespace-pre-wrap">
                  {part.text}
                </span>
              );
            }

            return (
              <div key={`i-${idx}`} className="my-2">
                <a
                  href={part.url}
                  target="_blank"
                  rel="noreferrer"
                  className={`inline-block ${isUser ? "max-w-full" : "max-w-[11rem]"}`}
                >
                  <img
                    src={part.url}
                    alt={part.alt || "image"}
                    loading="lazy"
                    className={
                      isUser
                        ? "max-w-full h-auto rounded-md border border-gray-200 dark:border-gray-600"
                        : "w-44 max-w-full h-28 object-cover rounded-md border border-gray-200 dark:border-gray-600"
                    }
                  />
                </a>
                <a
                  href={part.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 block text-[11px] underline opacity-80 break-all"
                >
                  {part.url}
                </a>
              </div>
            );
          })}
        </div>
        {message.isStreaming && !message.content && (
          <div className="flex gap-1 py-1">
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" />
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce [animation-delay:0.1s]" />
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce [animation-delay:0.2s]" />
          </div>
        )}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-2">
            {message.toolCalls.map((tc, idx) => (
              <McpToolCall
                key={`${tc.tool_call_id}-${idx}`}
                toolCall={tc}
              />
            ))}
          </div>
        )}
        {message.isStreaming && (
          <span className="inline-block w-1.5 h-4 bg-gray-400 animate-pulse ml-0.5 align-text-bottom" />
        )}
      </div>
    </div>
  );
}
