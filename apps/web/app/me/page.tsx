"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  GlobalNav,
  SubNavFrosted,
  Tile,
  PillButton,
  Switch,
  BottomNav,
  Footer,
  SkeletonBlock,
} from "@/components/ui";
import {
  getMe,
  pauseSharing,
  type UserProfile,
  createCard,
  getCards,
  updateCard,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export default function MeHubPage() {
  useRequireAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [pausing, setPausing] = useState(false);

  // Phone fast-control
  const [phoneMode, setPhoneMode] = useState("normal");
  const [batteryPct, setBatteryPct] = useState<number | string>("");
  const [savingPhone, setSavingPhone] = useState(false);
  const [phoneMsg, setPhoneMsg] = useState("");
  const [phoneRecord, setPhoneRecord] = useState<any | null>(null);

  async function loadProfile() {
    setLoading(true);
    try {
      const data = await getMe();
      setProfile(data);
      setIsPaused(!!data.sharing_paused?.active);
      const phones = await getCards("phone");
      const phone = Array.isArray(phones) ? phones[0] : null;
      if (phone) {
        setPhoneRecord(phone);
        setPhoneMode(phone.mode || "normal");
        setBatteryPct(phone.battery_pct ?? "");
      }
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProfile();
  }, []);

  async function handleTogglePause(val: boolean) {
    setPausing(true);
    try {
      const result = await pauseSharing(val);
      setIsPaused(result.sharing_paused.active);
    } finally {
      setPausing(false);
    }
  }

  async function handleSavePhone() {
    setSavingPhone(true);
    try {
      const payload = {
        mode: phoneMode,
        battery_pct: batteryPct !== "" ? Number(batteryPct) : phoneRecord?.battery_pct ?? 100,
        may_go_offline: batteryPct !== "" ? Number(batteryPct) <= 10 : phoneRecord?.may_go_offline ?? false,
      };
      if (phoneRecord) {
        const saved = await updateCard("phone", phoneRecord._id || profile?.id || "", {
          ...payload,
          version: phoneRecord.version || 1,
        });
        setPhoneRecord(saved.record || saved);
      } else {
        const saved = await createCard("phone", payload);
        setPhoneRecord(saved.record || null);
      }
      setPhoneMsg("✓ Phone state updated");
      setTimeout(() => setPhoneMsg(""), 2000);
    } finally {
      setSavingPhone(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] pb-28">
      <GlobalNav />
      <SubNavFrosted
        title="Me & Cards"
        action={
          <Link href="/me/profile">
            <PillButton variant="ghost" className="!py-1 !px-3 text-[14px]">
              Profile ⚙️
            </PillButton>
          </Link>
        }
      />

      <main className="mx-auto flex max-w-[390px] flex-col gap-4 px-4 py-5">
        {loading ? (
          <SkeletonBlock className="h-32 w-full" />
        ) : (
          /* Pause Sharing Master Switch */
          <Tile tone="parchment" className="p-4 border-2 border-[var(--hairline)]">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-[17px] font-semibold text-[var(--ink)]">
                  {isPaused ? "Sharing is PAUSED" : "Live Sharing Active"}
                </h3>
                <p className="text-[13px] text-[var(--ink-muted-80)]">
                  {isPaused
                    ? "Your circle sees blank status."
                    : "Your circle sees only what you have granted."}
                </p>
              </div>
              <Switch checked={isPaused} onChange={handleTogglePause} />
            </div>
          </Tile>
        )}

        {/* Card Management List */}
        <Tile tone="light" className="p-4">
          <h2 className="text-[14px] font-semibold uppercase tracking-wider text-[var(--ink-muted-80)] mb-3">
            Life Context Cards
          </h2>

          <div className="flex flex-col gap-3">
            <Link
              href="/me/schedule"
              className="flex items-center justify-between rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3 transition-transform active:scale-[0.98]"
            >
              <div>
                <p className="text-[16px] font-semibold text-[var(--ink)]">🗓 Schedule & Routine</p>
                <p className="text-[12px] text-[var(--ink-muted-48)]">
                  Recurring lectures, study blocks & exceptions
                </p>
              </div>
              <span className="text-[13px] font-semibold text-[var(--primary)]">Manage →</span>
            </Link>

            <Link
              href="/me/exam"
              className="flex items-center justify-between rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3 transition-transform active:scale-[0.98]"
            >
              <div>
                <p className="text-[16px] font-semibold text-[var(--ink)]">📝 Exams & Tests</p>
                <p className="text-[12px] text-[var(--ink-muted-48)]">
                  Exam season, sessions & pre/post buffers
                </p>
              </div>
              <span className="text-[13px] font-semibold text-[var(--primary)]">Manage →</span>
            </Link>

            <Link
              href="/me/travel"
              className="flex items-center justify-between rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3 transition-transform active:scale-[0.98]"
            >
              <div>
                <p className="text-[16px] font-semibold text-[var(--ink)]">✈️ Travel & ETA</p>
                <p className="text-[12px] text-[var(--ink-muted-48)]">
                  Active journey, companions & Arrival Watch
                </p>
              </div>
              <span className="text-[13px] font-semibold text-[var(--primary)]">Manage →</span>
            </Link>

            <Link
              href="/me/messages"
              className="flex items-center justify-between rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3 transition-transform active:scale-[0.98]"
            >
              <div>
                <p className="text-[16px] font-semibold text-[var(--ink)]">💬 Message Drops & Promises</p>
                <p className="text-[12px] text-[var(--ink-muted-48)]">
                  Context broadcasts and callback promises
                </p>
              </div>
              <span className="text-[13px] font-semibold text-[var(--primary)]">Manage →</span>
            </Link>
          </div>
        </Tile>

        {/* Quick Phone State Editor */}
        <Tile id="phone-card" tone="parchment" className="p-4 scroll-mt-20">
          <h3 className="text-[16px] font-semibold text-[var(--ink)] mb-1">⚡ Quick Phone State</h3>
          <p className="text-[12px] text-[var(--ink-muted-80)] mb-3">
            Broadcast ringer mode and battery level to your trusted circle.
          </p>

          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-[14px] text-[var(--ink)]">Ringer Mode</span>
              <div className="flex gap-1">
                {(["normal", "silent", "dnd"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setPhoneMode(m)}
                    className={`rounded-[var(--r-sm)] px-2.5 py-1 text-[12px] capitalize font-medium ${
                      phoneMode === m
                        ? "bg-[var(--primary)] text-[var(--on-primary)]"
                        : "bg-[var(--canvas)] text-[var(--ink-muted-80)] border border-[var(--hairline)]"
                    }`}
                  >
                  {m === "normal" ? "Ring" : m === "silent" ? "Silent" : "DND"}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-[14px] text-[var(--ink)]">Battery %</span>
              <input
                type="number"
                min="0"
                max="100"
                placeholder="e.g. 23"
                value={batteryPct}
                onChange={(e) => setBatteryPct(e.target.value)}
                className="w-20 rounded-[var(--r-sm)] border border-[var(--hairline)] bg-[var(--canvas)] px-2 py-1 text-[14px] text-center"
              />
            </div>

            {phoneMsg && <p className="text-[13px] font-semibold text-[var(--primary)] text-center">{phoneMsg}</p>}

            <PillButton
              variant="primary"
              onClick={handleSavePhone}
              disabled={savingPhone}
              className="w-full !py-2 text-[15px]"
            >
              {savingPhone ? "Updating..." : "Update Phone State"}
            </PillButton>
          </div>
        </Tile>

        <Footer />
      </main>

      <BottomNav current="me" />
    </div>
  );
}
