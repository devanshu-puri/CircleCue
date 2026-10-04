"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Tile, PillButton, InputField, Footer } from "@/components/ui";
import { login, loginDemo } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) {
      setError("Please fill in both email and password.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Login failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDemo() {
    setDemoLoading(true);
    setError(null);
    try {
      await loginDemo();
      router.push("/");
    } catch (err: any) {
      setError(err.message || "The demo is unavailable right now.");
    } finally {
      setDemoLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] flex flex-col justify-between px-4 py-8">
      <header className="mx-auto max-w-[390px] w-full text-center">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--r-sm)] border border-[var(--hairline)] bg-[var(--surface-tile-1)] text-lg text-[var(--on-dark)] font-bold">
          C
        </span>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-[28px] font-semibold text-[var(--ink)]">
          Welcome to CircleCue
        </h1>
        <p className="mt-1 text-[14px] text-[var(--ink-muted-80)]">
          Private, permission-based life context for trusted people.
        </p>
      </header>

      <main className="mx-auto max-w-[390px] w-full my-auto">
        <Tile tone="parchment" className="p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <InputField
              label="Email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
            <InputField
              label="Password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />

            {error && (
              <p className="text-[13px] text-[var(--danger)] leading-tight">{error}</p>
            )}

            <PillButton type="submit" variant="primary" disabled={loading} className="w-full mt-2">
              {loading ? "Signing in..." : "Sign In"}
            </PillButton>
          </form>

          <div className="my-5 border-t border-[var(--hairline)]" />
          <p className="mb-3 text-center text-[14px] text-[var(--ink-muted-80)]">
            Just looking? Explore the app without an account. Demo changes are disabled.
          </p>
          <PillButton
            type="button"
            variant="ghost"
            disabled={demoLoading}
            onClick={handleDemo}
            className="w-full"
          >
            {demoLoading ? "Opening demo…" : "Explore read-only demo"}
          </PillButton>

          <div className="mt-6 text-center text-[14px] text-[var(--ink-muted-80)]">
            Don’t have an account?{" "}
            <Link href="/register" className="font-semibold text-[var(--primary)] hover:underline">
              Create account
            </Link>
          </div>
        </Tile>
      </main>

      <Footer />
    </div>
  );
}
