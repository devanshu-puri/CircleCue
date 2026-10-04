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
  const [editingTravel, setEditingTravel] = useState(false);
  const [destination, setDestination] = useState("");
  const [etaTime, setEtaTime] = useState("");
  const [returnTime, setReturnTime] = useState("");
  const [companion, setCompanion] = useState("");
  const [companionPhone, setCompanionPhone] = useState("");
  const [mode, setMode] = useState("cab");
  const [checkOnMe, setCheckOnMe] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function localDateTime(value?: string | null) {
    if (!value) return "";
    const date = new Date(value);
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
  }

  function resetForm(travel?: any) {
    const metadata = travel?.metadata || {};
    setDestination(metadata.destination || "");
    setEtaTime(localDateTime(metadata.eta || travel?.expected_end_at));
    setReturnTime(localDateTime(metadata.expected_return_at));
    setCompanion(metadata.companions?.[0] || "");
    setCompanionPhone(metadata.companion_phone || "");
    setMode(metadata.mode || "cab");
    setCheckOnMe(Boolean(travel?.check_on_me?.enabled));
    setError("");
    setNotice("");
  }

  async function loadTravel() {
    setLoading(true);
    try {
      const res = await getCards("travel");
      const records = Array.isArray(res) ? res : [];
      const current = records
        .filter((item: any) => !["COMPLETED", "CANCELLED", "EXPIRED"].includes(item.status))
        .sort((a: any, b: any) => new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime())[0];
      setActiveTravel(current || null);
    } catch (err: any) {
      setError(err?.message || "Could not load your saved journeys.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTravel();
  }, []);

  async function handleStartTravel(e: React.FormEvent) {
    e.preventDefault();
    if (!destination || !etaTime) return;
    setSaving(true);
    setError("");
    try {
      const eta = new Date(etaTime).toISOString();
      const expectedReturn = returnTime ? new Date(returnTime).toISOString() : null;
      const metadata = {
        kind: "travel",
        destination,
        eta,
        mode,
        companions: companion.trim() ? [companion.trim()] : [],
        companion_phone: companionPhone.trim() || null,
        expected_return_at: expectedReturn,
      };
      const payload: Record<string, any> = {
        type: "TRAVEL",
        title: `Going to ${destination}`,
        expected_end_at: eta,
        metadata,
        check_on_me: { enabled: checkOnMe, grace_min: 15, escalate_min: 15 },
      };
      if (editingTravel && activeTravel) {
        await updateCard("travel", activeTravel._id || activeTravel.id, {
          ...payload,
          version: activeTravel.version || 1,
        });
      } else {
        await createCard("travel", {
          ...payload,
          status: "ACTIVE",
          phase: "travelling",
          start_at: new Date().toISOString(),
        });
      }
      setModalOpen(false);
      setNotice(editingTravel ? "Journey updated." : "Journey saved.");
      await loadTravel();
    } catch (err: any) {
      setError(err.message || "Could not save this journey.");
    } finally {
      setSaving(false);
    }
  }

  function openStartTravel() {
    setEditingTravel(false);
    resetForm();
    setModalOpen(true);
  }

  async function handleUpdatePhase(phase: "arrived" | "delayed" | "cancelled") {
    if (!activeTravel) return;
    setError("");
    try {
      const itemId = activeTravel._id || activeTravel.id;
      const version = activeTravel.version || 1;
      if (phase === "arrived") {
        await updateCard("travel", itemId, {
          status: "COMPLETED",
          phase: "arrived",
          version,
        });
      } else if (phase === "cancelled") {
        await updateCard("travel", itemId, {
          status: "CANCELLED",
          version,
        });
      } else {
        const baseEta = new Date(activeTravel.metadata?.eta || activeTravel.expected_end_at).getTime();
        await updateCard("travel", itemId, {
          new_eta: new Date(baseEta + 30 * 60_000).toISOString(),
          version,
        });
      }
      await loadTravel();
    } catch (caught: any) {
      setError(caught.message || "Could not update this journey.");
    }
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] pb-28">
      <GlobalNav />
      <SubNavFrosted title="Travel" action={<Link href="/me"><span className="text-[14px] font-semibold text-[var(--primary)]">← All cards</span></Link>} />

      <main className="mx-auto flex max-w-[390px] flex-col gap-4 px-4 py-5">
        <div className="flex items-center justify-between">
          <p className="text-[13px] text-[var(--ink-muted-80)]">
            Share journey progress and let Arrival Watch guard your safety.
          </p>
          {!activeTravel && (
            <PillButton variant="primary" onClick={openStartTravel} className="!py-1 !px-3 text-[14px]">
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
              <PillButton variant="primary" onClick={openStartTravel} className="mt-4">
                Start a Journey
              </PillButton>
            </div>
          ) : (
            <div className="flex flex-col gap-3 rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-4">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-semibold uppercase tracking-wider text-[var(--primary)]">
                  {activeTravel.phase || "In Transit"}
                </span>
                {activeTravel.check_on_me?.enabled && (
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

              {activeTravel.metadata?.companions?.[0] && (
                <p className="text-[13px] text-[var(--ink-muted-48)]">
                  With: {activeTravel.metadata.companions[0]}
                </p>
              )}
              {activeTravel.metadata?.expected_return_at && <p className="text-[14px] text-[var(--ink-muted-80)]">Expected return: {new Date(activeTravel.metadata.expected_return_at).toLocaleString()}</p>}

              {/* Lifecycle control buttons */}
              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[var(--hairline)]">
                <PillButton variant="ghost" onClick={() => { setEditingTravel(true); resetForm(activeTravel); setModalOpen(true); }} className="!py-1.5 text-[13px]">
                  Edit details
                </PillButton>
              </div>
              <div className="grid grid-cols-3 gap-2">
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

        {error && !modalOpen && <p role="alert" className="text-[13px] text-[var(--danger)]">{error}</p>}
        {notice && <p role="status" className="text-[13px] text-[var(--primary)]">{notice}</p>}

        <Footer />
      </main>

      {/* Start Travel Modal */}
      <BottomSheet isOpen={modalOpen} onClose={() => { setModalOpen(false); setEditingTravel(false); }} title={editingTravel ? "Update Travel" : "Start Travel"}>
        <form onSubmit={handleStartTravel} className="flex flex-col gap-4 pb-2">
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

          <InputField
            label="Companion phone (optional)"
            type="tel"
            maxLength={20}
            placeholder="Phone number"
            value={companionPhone}
            onChange={(e) => setCompanionPhone(e.target.value)}
          />

          <InputField
            label="Expected arrival at destination"
            type="datetime-local"
            value={etaTime}
            onChange={(e) => setEtaTime(e.target.value)}
            required
          />

          <InputField
            label="Expected return (optional)"
            type="datetime-local"
            value={returnTime}
            onChange={(e) => setReturnTime(e.target.value)}
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

          <PillButton type="submit" variant="primary" disabled={saving} className="sticky bottom-0 w-full mt-2">
            {saving ? "Saving journey..." : editingTravel ? "Save Journey" : "Start Journey"}
          </PillButton>
          {error && <p className="text-[13px] text-[var(--danger)]">{error}</p>}
        </form>
      </BottomSheet>

      <BottomNav current="me" />
    </div>
  );
}
