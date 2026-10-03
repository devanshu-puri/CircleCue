import "./globals.css";
import React from "react";

export const metadata = {
  title: "CircleCue",
  description: "Private, permission-based life-context network for trusted people.",
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <main className="min-h-screen bg-[var(--canvas)] text-[var(--body)]">
          {children}
        </main>
      </body>
    </html>
  );
}
