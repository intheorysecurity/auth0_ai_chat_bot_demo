"use client";

import { getAccessToken, useUser } from "@auth0/nextjs-auth0";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getAuthedJson } from "@/lib/api";

type UserClaims = Record<string, unknown>;

function pretty(value: unknown) {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

export default function ProfilePage() {
  const { user, isLoading: authLoading } = useUser();
  const [accessToken, setAccessToken] = useState<string | undefined>();
  const [tokenLoading, setTokenLoading] = useState(true);

  const [claims, setClaims] = useState<UserClaims | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadToken() {
      if (authLoading) return;
      if (!user) {
        if (!cancelled) {
          setTokenLoading(false);
          setAccessToken(undefined);
        }
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

  useEffect(() => {
    let cancelled = false;
    async function loadClaims() {
      setLoading(true);
      setError(null);
      setClaims(null);

      if (!accessToken) {
        setLoading(false);
        return;
      }

      try {
        const data = await getAuthedJson<{ user: UserClaims }>(
          "/api/auth/me",
          accessToken
        );
        if (!cancelled) setClaims(data.user);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Unknown error";
        if (!cancelled) setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    if (!tokenLoading) {
      loadClaims();
    }

    return () => {
      cancelled = true;
    };
  }, [accessToken, tokenLoading]);

  const basic = useMemo(() => {
    const c = claims || {};
    const rows: Array<[string, unknown]> = [
      ["Name", c["name"]],
      ["Email", c["email"]],
      ["Subject (sub)", c["sub"]],
      ["Issuer (iss)", c["iss"]],
      ["Audience (aud)", c["aud"]],
    ];
    return rows.filter(([, v]) => v !== undefined && v !== null && v !== "");
  }, [claims]);

  const showSpinner = authLoading || tokenLoading || loading;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-3xl mx-auto px-6 py-10 space-y-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
              Profile
            </h1>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              Verified identity info from the backend (`/api/auth/me`).
            </p>
          </div>
          <Link
            href="/chat"
            className="text-sm px-3 py-2 rounded-md border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200 hover:bg-white/60 dark:hover:bg-gray-800 transition-colors"
          >
            Back to chat
          </Link>
        </div>

        {showSpinner ? (
          <div className="flex items-center gap-3 text-sm text-gray-600 dark:text-gray-300">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-gray-900 dark:border-gray-100" />
            Loading…
          </div>
        ) : null}

        {!user && !authLoading ? (
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
            <div className="text-sm text-gray-800 dark:text-gray-200">
              You’re not signed in.
            </div>
            <div className="mt-3">
              <a
                href="/auth/login"
                className="inline-block text-sm px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                Sign in
              </a>
            </div>
          </div>
        ) : null}

        {user && !accessToken && !showSpinner ? (
          <div className="rounded-lg border border-amber-200 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-900/20 p-5">
            <div className="text-sm text-amber-900 dark:text-amber-200 font-medium">
              Couldn’t retrieve an access token.
            </div>
            <div className="text-sm text-amber-800 dark:text-amber-200/80 mt-1">
              Try logging out and back in.
            </div>
            <div className="mt-3">
              <a
                href="/auth/logout"
                className="inline-block text-sm px-4 py-2 bg-white dark:bg-gray-800 rounded-md border border-amber-200 dark:border-amber-900/60 text-amber-900 dark:text-amber-100 hover:bg-amber-100/60 dark:hover:bg-amber-900/30 transition-colors"
              >
                Sign out
              </a>
            </div>
          </div>
        ) : null}

        {error && !showSpinner ? (
          <div className="rounded-lg border border-red-200 dark:border-red-900/60 bg-red-50 dark:bg-red-900/20 p-5">
            <div className="text-sm text-red-900 dark:text-red-200 font-medium">
              Failed to load profile
            </div>
            <div className="mt-2 text-xs text-red-900/90 dark:text-red-200/90 whitespace-pre-wrap">
              {error}
            </div>
          </div>
        ) : null}

        {claims && !showSpinner ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
              <div className="text-sm font-medium text-gray-900 dark:text-white">
                Basics
              </div>
              <div className="mt-3 divide-y divide-gray-100 dark:divide-gray-700">
                {basic.length === 0 ? (
                  <div className="py-3 text-sm text-gray-600 dark:text-gray-300">
                    No standard claims found.
                  </div>
                ) : (
                  basic.map(([k, v]) => (
                    <div key={k} className="py-3 flex gap-4">
                      <div className="w-40 text-xs text-gray-500 dark:text-gray-400">
                        {k}
                      </div>
                      <div className="flex-1 text-sm text-gray-900 dark:text-gray-100 break-words">
                        {pretty(v)}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
              <div className="text-sm font-medium text-gray-900 dark:text-white">
                Raw claims
              </div>
              <pre className="mt-3 text-xs bg-gray-50 dark:bg-gray-900/40 border border-gray-200 dark:border-gray-700 rounded-md p-4 overflow-auto text-gray-900 dark:text-gray-100">
                {JSON.stringify(claims, null, 2)}
              </pre>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

