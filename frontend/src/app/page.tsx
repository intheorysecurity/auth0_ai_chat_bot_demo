"use client";

import { useUser } from "@auth0/nextjs-auth0";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Home() {
  const { user, isLoading } = useUser();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && user) {
      router.push("/chat");
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-md text-center space-y-6">
        <h1 className="text-4xl font-bold text-gray-900 dark:text-white">
          AI Chat Bot
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          A demo chatbot with pluggable LLMs (Claude, OpenAI, Ollama) and MCP
          server integration.
        </p>
        <a
          href="/auth/login"
          className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          Sign In
        </a>
      </div>
    </div>
  );
}
