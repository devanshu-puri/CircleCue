"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Tile, PillButton, InputField, Footer } from "@/components/ui";
import { register } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name || !email || !password) {
      setError("Please fill in all fields.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
      await register(name, email, password, tz);
      router.push("/login");
    } catch (err: any) {
      setError(err.message || "Registration failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] flex flex-col justify-between px-4 py-8">
      <header className="mx-auto max-w-[390px] w-full text-center">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--r-sm)] border border-[var(--hairline)] bg-[var(--surface-tile-1)] text-lg text-[var(--on-dark)] font-bold">
          C
        </span>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-[28px] font-semibold text-[var(--ink)]">
          Join CircleCue
        </h1>
        <p className="mt-1 text-[14px] text-[var(--ink-muted-80)]">
          Share your availability naturally, without endless calls.
        </p>
      </header>

      <main className="mx-auto max-w-[390px] w-full my-auto">
        <Tile tone="parchment" className="p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <InputField
              label="Your name"
              type="text"
              placeholder="e.g. Arjun Kumar"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
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
              autoComplete="new-password"
            />

            {error && (
              <p className="text-[13px] text-[var(--danger)] leading-tight">{error}</p>
            )}

            <PillButton type="submit" variant="primary" disabled={loading} className="w-full mt-2">
              {loading ? "Creating account..." : "Create Account"}
            </PillButton>
          </form>

          <div className="mt-6 text-center text-[14px] text-[var(--ink-muted-80)]">
            Already have an account?{" "}
            <Link href="/login" className="font-semibold text-[var(--primary)] hover:underline">
              Sign in
            </Link>
          </div>
        </Tile>
      </main>

      <Footer />
    </div>
  );
}
