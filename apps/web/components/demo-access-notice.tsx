"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { isReadOnlyDemoSession } from "@/lib/api";

export function DemoAccessNotice() {
  const [readOnly, setReadOnly] = useState(false);
  const [attemptedWrite, setAttemptedWrite] = useState(false);

  useEffect(() => {
    const syncSession = () => setReadOnly(isReadOnlyDemoSession());
    const showWriteNotice = () => setAttemptedWrite(true);
    syncSession();
    window.addEventListener("circlecue:auth-changed", syncSession);
    window.addEventListener("circlecue:demo-write-blocked", showWriteNotice);
    return () => {
      window.removeEventListener("circlecue:auth-changed", syncSession);
      window.removeEventListener("circlecue:demo-write-blocked", showWriteNotice);
    };
  }, []);

  if (!readOnly) return null;

  return (
    <aside
      aria-live={attemptedWrite ? "assertive" : "polite"}
      className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2 border-b border-[var(--hairline)] bg-[var(--canvas-parchment)] px-4 py-3 text-center text-[14px] text-[var(--ink)]"
    >
      <span>
        {attemptedWrite
          ? "This demo is view-only. Sign in or create an account to make changes."
          : "You’re viewing the read-only demo."}
      </span>
      <Link
        href="/login"
        className="inline-flex min-h-11 items-center justify-center rounded-[var(--r-pill)] px-4 font-semibold text-[var(--primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary-focus)]"
      >
        Sign in
      </Link>
      <Link
        href="/register"
        className="inline-flex min-h-11 items-center justify-center rounded-[var(--r-pill)] bg-[var(--primary)] px-4 text-[var(--on-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary-focus)]"
      >
        Create account
      </Link>
    </aside>
  );
}
