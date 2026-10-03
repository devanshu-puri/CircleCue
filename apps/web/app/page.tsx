import React from "react";

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6 text-center">
      <div className="max-w-md space-y-4">
        <h1 className="t-display-lg text-[var(--ink)]">CircleCue</h1>
        <p className="t-lead-airy text-[var(--ink-muted-48)]">
          Know what matters about the people you care about, without constantly calling or asking.
        </p>
        <div className="pt-4">
          <span className="inline-block rounded-[var(--r-pill)] bg-[var(--surface-pearl)] px-4 py-2 t-caption text-[var(--primary)] border border-[var(--hairline)]">
            System Online &bull; Local Mode
          </span>
        </div>
      </div>
    </div>
  );
}
