"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  GlobalNav,
  SubNavFrosted,
  Tile,
  PillButton,
  BottomSheet,
  BottomNav,
  Footer,
  SkeletonBlock,
} from "@/components/ui";
import { getCards, createCard, deleteCard } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export default function MessagesCardPage() {
  useRequireAuth();
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [text, setText] = useState("");
  const [promiseHours, setPromiseHours] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  async function loadMessages() {
    setLoading(true);
    try {
      const res = await getCards("message");
      setMessages(res.messages || []);
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMessages();
  }, []);

  async function handleDropMessage(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSaving(true);
    try {
      const promise_at = promiseHours
        ? new Date(Date.now() + promiseHours * 3600 * 1000).toISOString()
        : null;
      await createCard("message", {
        text: text.trim(),
        audience: [],
        promise_at,
      });
      setModalOpen(false);
      setText("");
      setPromiseHours(null);
      loadMessages();
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteMessage(id: string, version: number = 1) {
    await deleteCard("message", id, version);
    loadMessages();
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] pb-28">
      <GlobalNav />
      <SubNavFrosted
        title="Messages"
        action={
          <Link href="/me">
            <span className="text-[14px] font-semibold text-[var(--primary)]">← Back</span>
          </Link>
        }
      />

      <main className="mx-auto flex max-w-[390px] flex-col gap-4 px-4 py-5">
        <div className="flex items-center justify-between">
          <p className="text-[13px] text-[var(--ink-muted-80)]">
            Drop context notes or promises to reply without starting chats.
          </p>
          <PillButton variant="primary" onClick={() => setModalOpen(true)} className="!py-1 !px-3 text-[14px]">
            + Drop Note
          </PillButton>
        </div>

        <Tile tone="light" className="p-4">
          <h2 className="text-[16px] font-semibold text-[var(--ink)] mb-3">
            Active Context Messages ({messages.length})
          </h2>

          {loading ? (
            <SkeletonBlock className="h-32 w-full" />
          ) : messages.length === 0 ? (
            <div className="py-8 text-center text-[14px] text-[var(--ink-muted-48)]">
              No active context messages.
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {messages.map((m) => (
                <div
                  key={m._id}
                  className="flex flex-col gap-2 rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3"
                >
                  <div className="flex items-start justify-between">
                    <p className="text-[15px] font-semibold text-[var(--ink)]">{m.text}</p>
                    <button
                      type="button"
                      onClick={() => handleDeleteMessage(m._id, m.version || 1)}
                      className="text-[12px] font-semibold text-[var(--danger)] hover:underline"
                    >
                      Dismiss
                    </button>
                  </div>

                  {m.promise_at && (
                    <div className="flex items-center gap-1 text-[12px] text-[var(--primary)]">
                      <span>⏳ Promised by:</span>
                      <span>{new Date(m.promise_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>
                    </div>
                  )}

                  <p className="text-[11px] text-[var(--ink-muted-48)]">
                    Audience: {m.audience?.length ? `${m.audience.length} people` : "All granted connections"}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Tile>

        <Footer />
      </main>

      {/* Drop Note Bottom Sheet */}
      <BottomSheet isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Drop a Note">
        <form onSubmit={handleDropMessage} className="flex flex-col gap-4">
          <div>
            <label className="text-[14px] text-[var(--ink-muted-80)] block mb-1">Context Note</label>
            <textarea
              rows={3}
              placeholder="e.g. In transit, will reply in the evening"
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="w-full rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3 text-[15px] text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-focus)]"
              required
            />
          </div>

          <div>
            <label className="text-[14px] text-[var(--ink-muted-80)] block mb-1">
              Callback Promise (optional)
            </label>
            <div className="flex gap-2">
              {[
                { label: "None", val: null },
                { label: "In 1h", val: 1 },
                { label: "In 3h", val: 3 },
                { label: "Tonight", val: 6 },
              ].map((opt) => (
                <button
                  key={opt.label}
                  type="button"
                  onClick={() => setPromiseHours(opt.val)}
                  className={`rounded-[var(--r-pill)] px-3 py-1 text-[13px] border ${
                    promiseHours === opt.val
                      ? "bg-[var(--primary)] text-[var(--on-primary)] border-[var(--primary)]"
                      : "bg-[var(--canvas)] text-[var(--ink-muted-80)] border-[var(--hairline)]"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <PillButton type="submit" variant="primary" disabled={saving} className="w-full mt-2">
            {saving ? "Posting..." : "Drop Note"}
          </PillButton>
        </form>
      </BottomSheet>

      <BottomNav current="me" />
    </div>
  );
}
