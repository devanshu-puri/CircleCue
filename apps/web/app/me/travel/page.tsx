"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  GlobalNav,
  SubNavFrosted,
  Tile,
  PillButton,
  InputField,
  BottomSheet,
  BottomNav,
  Footer,
  SkeletonBlock,
} from "@/components/ui";
import { getCards, createCard, updateCard } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export default function TravelCardPage() {
  useRequireAuth();
  const [activeTravel, setActiveTravel] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  // Form State
  const [modalOpen, setModalOpen] = useState(false);
  const [destination, setDestination] = useState("");
  const [etaTime, setEtaTime] = useState("");
  const [companion, setCompanion] = useState("");
  const [mode, setMode] = useState("cab");
  const [checkOnMe, setCheckOnMe] = useState(true);
  const [saving, setSaving] = useState(false);

  async function loadTravel() {
    setLoading(true);
    try {
      const res = await getCards("travel");
      setActiveTravel(res.active || null);
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTravel();
  }, []);

  async function handleStartTravel(e: React.FormEvent) {
    e.preventDefault();
    if (!destination) return;
    setSaving(true);
    try {
      const payload = {
        title: `Going to ${destination}`,
        destination,
        depart_at: new Date().toISOString(),
        expected_eta_at: etaTime
          ? new Date(Date.now() + 2 * 3600 * 1000).toISOString()
          : new Date(Date.now() + 3600 * 1000).toISOString(),
        companion: companion || null,
        mode,
        check_on_me: {
          enabled: checkOnMe,
          grace_min: 15,
          escalate_min: 15,
        },
      };
      await createCard("travel", payload);
      setModalOpen(false);
      loadTravel();
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdatePhase(phase: "arrived" | "delayed" | "cancelled") {
    if (!activeTravel) return;
    if (phase === "arrived") {
      await updateCard("travel", activeTravel._id, {
        status: "COMPLETED",
        phase: "arrived",
        version: activeTravel.version || 1,
      });
    } else if (phase === "cancelled") {
      await updateCard("travel", activeTravel._id, {
        status: "CANCELLED",
        phase: "planned",
        version: activeTravel.version || 1,
      });
    } else if (phase === "delayed") {
      await updateCard("travel", activeTravel._id, {
        phase: "delayed",
        delay_min: 30,
        version: activeTravel.version || 1,
      });
    }
    loadTravel();
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] pb-28">
      <GlobalNav />
      <SubNavFrosted
        title="Travel"
        action={
          <Link href="/me">
            <span className="text-[14px] font-semibold text-[var(--primary)]">← Back</span>
          </Link>
        }
      />

      <main className="mx-auto flex max-w-[390px] flex-col gap-4 px-4 py-5">
        <div className="flex items-center justify-between">
          <p className="text-[13px] text-[var(--ink-muted-80)]">
            Share journey progress and let Arrival Watch guard your safety.
          </p>
          {!activeTravel && (
            <PillButton variant="primary" onClick={() => setModalOpen(true)} className="!py-1 !px-3 text-[14px]">
              + Start Travel
            </PillButton>
          )}
        </div>

        <Tile tone="light" className="p-4">
          <h2 className="text-[16px] font-semibold text-[var(--ink)] mb-3">Active Journey</h2>

          {loading ? (
            <SkeletonBlock className="h-32 w-full" />
          ) : !activeTravel ? (
            <div className="py-8 text-center text-[14px] text-[var(--ink-muted-48)]">
              <p>Not travelling right now.</p>
              <PillButton variant="primary" onClick={() => setModalOpen(true)} className="mt-4">
                Start a Journey
              </PillButton>
            </div>
          ) : (
            <div className="flex flex-col gap-3 rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-4">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-semibold uppercase tracking-wider text-[var(--primary)]">
                  {activeTravel.phase || "In Transit"}
                </span>
                {activeTravel.metadata?.check_on_me?.enabled && (
                  <span className="rounded-[var(--r-pill)] bg-[var(--surface-pearl)] px-2 py-0.5 text-[11px] font-medium text-[var(--ink)]">
                    🛡️ Arrival Watch Active
                  </span>
                )}
              </div>

              <h3 className="text-[20px] font-semibold text-[var(--ink)]">
                {activeTravel.metadata?.destination || activeTravel.title || "Travelling"}
              </h3>

              <p className="text-[14px] text-[var(--ink-muted-80)]">
                ETA:{" "}
                {activeTravel.expected_end_at
                  ? new Date(activeTravel.expected_end_at).toLocaleTimeString([], {
                      hour: "numeric",
                      minute: "2-digit",
                    })
                  : "Not set"}
              </p>

              {activeTravel.metadata?.companion && (
                <p className="text-[13px] text-[var(--ink-muted-48)]">
                  With: {activeTravel.metadata.companion}
                </p>
              )}

              {/* Lifecycle control buttons */}
              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[var(--hairline)]">
                <PillButton variant="primary" onClick={() => handleUpdatePhase("arrived")} className="!py-1.5 text-[13px]">
                  Arrived ✓
                </PillButton>
                <PillButton variant="ghost" onClick={() => handleUpdatePhase("delayed")} className="!py-1.5 text-[13px]">
                  +30m Delay
                </PillButton>
                <PillButton variant="danger" onClick={() => handleUpdatePhase("cancelled")} className="!py-1.5 text-[13px]">
                  Cancel
                </PillButton>
              </div>
            </div>
          )}
        </Tile>

        <Footer />
      </main>

      {/* Start Travel Modal */}
      <BottomSheet isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Start Travel">
        <form onSubmit={handleStartTravel} className="flex flex-col gap-4">
          <InputField
            label="Destination"
            placeholder="e.g. Home, Delhi, Campus"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            required
          />

          <InputField
            label="Companion (optional)"
            placeholder="e.g. Rahul"
            value={companion}
            onChange={(e) => setCompanion(e.target.value)}
          />

          <div>
            <label className="text-[14px] text-[var(--ink-muted-80)] block mb-1">Mode of Transport</label>
            <div className="flex gap-2">
              {(["cab", "train", "flight", "car", "walking"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`rounded-[var(--r-pill)] px-3 py-1 text-[13px] capitalize border ${
                    mode === m
                      ? "bg-[var(--primary)] text-[var(--on-primary)] border-[var(--primary)]"
                      : "bg-[var(--canvas)] text-[var(--ink-muted-80)] border-[var(--hairline)]"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between py-2 border-t border-[var(--hairline)]">
            <div>
              <p className="text-[14px] font-semibold text-[var(--ink)]">Arrival Watch</p>
              <p className="text-[12px] text-[var(--ink-muted-48)]">
                Nudges if overdue; notifies circle if no response.
              </p>
            </div>
            <input
              type="checkbox"
              checked={checkOnMe}
              onChange={(e) => setCheckOnMe(e.target.checked)}
              className="h-5 w-5"
            />
          </div>

          <PillButton type="submit" variant="primary" disabled={saving} className="w-full mt-2">
            {saving ? "Starting travel..." : "Start Journey"}
          </PillButton>
        </form>
      </BottomSheet>

      <BottomNav current="me" />
    </div>
  );
}
