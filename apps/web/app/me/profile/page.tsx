"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  GlobalNav,
  SubNavFrosted,
  Tile,
  PillButton,
  InputField,
  BottomNav,
  Footer,
  SkeletonBlock,
  AvatarCircle,
} from "@/components/ui";
import {
  getMe,
  updateRoutinePrefs,
  exportData,
  deleteAccount,
  logout,
  type UserProfile,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export default function ProfilePage() {
  useRequireAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // Routine state
  const [wake, setWake] = useState("07:00");
  const [sleep, setSleep] = useState("23:00");
  const [minWindow, setMinWindow] = useState(10);
  const [savingRoutine, setSavingRoutine] = useState(false);
  const [copied, setCopied] = useState(false);
  const [routineMsg, setRoutineMsg] = useState("");
  const [exportJson, setExportJson] = useState<string | null>(null);

  async function loadProfile() {
    setLoading(true);
    try {
      const me = await getMe();
      setProfile(me);
      if (me.routine_prefs) {
        setWake(me.routine_prefs.wake || "07:00");
        setSleep(me.routine_prefs.sleep || "23:00");
        setMinWindow(me.routine_prefs.min_call_window_min || 10);
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

  function handleCopyCode() {
    if (!profile?.user_code) return;
    navigator.clipboard.writeText(profile.user_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleSaveRoutine(e: React.FormEvent) {
    e.preventDefault();
    setSavingRoutine(true);
    try {
      await updateRoutinePrefs({
        wake,
        sleep,
        min_call_window_min: Number(minWindow),
        buffer_min: 5,
      });
      setRoutineMsg("✓ Routine saved");
      setTimeout(() => setRoutineMsg(""), 2000);
    } finally {
      setSavingRoutine(false);
    }
  }

  async function handleExport() {
    const data = await exportData();
    setExportJson(JSON.stringify(data, null, 2));
  }

  async function handleDeleteAccount() {
    if (confirm("Are you sure you want to delete your account? All your data will be permanently wiped.")) {
      await deleteAccount();
      router.push("/login");
    }
  }

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] pb-28">
      <GlobalNav />
      <SubNavFrosted
        title="My Profile"
        action={
          <Link href="/me">
            <span className="text-[14px] font-semibold text-[var(--primary)]">← Back</span>
          </Link>
        }
      />

      <main className="mx-auto flex max-w-[390px] flex-col gap-4 px-4 py-5">
        {loading ? (
          <SkeletonBlock className="h-40 w-full" />
        ) : (
          /* Profile Card & Universal Code */
          <Tile tone="parchment" className="p-5 text-center">
            <div className="flex justify-center">
              <AvatarCircle name={profile?.name || "User"} size={64} />
            </div>
            <h2 className="mt-3 font-[family-name:var(--font-display)] text-[22px] font-semibold text-[var(--ink)]">
              {profile?.name}
            </h2>
            <p className="text-[13px] text-[var(--ink-muted-48)]">{profile?.email}</p>

            <div className="mt-4 inline-flex items-center gap-2 rounded-[var(--r-pill)] border border-[var(--hairline)] bg-[var(--canvas)] px-4 py-2">
              <span className="text-[12px] font-medium text-[var(--ink-muted-80)]">Universal Code:</span>
              <span className="font-mono text-[16px] font-bold text-[var(--primary)] tracking-wider">
                {profile?.user_code}
              </span>
              <button
                type="button"
                onClick={handleCopyCode}
                className="ml-1 rounded-full bg-[var(--surface-pearl)] px-2 py-0.5 text-[11px] font-medium text-[var(--ink)] active:scale-[0.95]"
              >
                {copied ? "Copied! ✓" : "Copy"}
              </button>
            </div>
          </Tile>
        )}

        {/* Routine Preferences */}
        <Tile tone="light" className="p-4">
          <h3 className="text-[16px] font-semibold text-[var(--ink)] mb-1">⏰ Daily Routine & Quiet Hours</h3>
          <p className="text-[12px] text-[var(--ink-muted-80)] mb-4">
            Used by CircleCue to automatically protect your sleep and call buffers.
          </p>

          <form onSubmit={handleSaveRoutine} className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <InputField
                label="Wake time"
                type="time"
                value={wake}
                onChange={(e) => setWake(e.target.value)}
                required
              />
              <InputField
                label="Sleep time"
                type="time"
                value={sleep}
                onChange={(e) => setSleep(e.target.value)}
                required
              />
            </div>

            <InputField
              label="Min call window (minutes)"
              type="number"
              min="5"
              max="60"
              value={minWindow}
              onChange={(e) => setMinWindow(Number(e.target.value))}
              required
            />

            {routineMsg && (
              <p className="text-[13px] font-semibold text-[var(--primary)] text-center">{routineMsg}</p>
            )}

            <PillButton type="submit" variant="primary" disabled={savingRoutine} className="w-full mt-1">
              {savingRoutine ? "Saving..." : "Save Routine"}
            </PillButton>
          </form>
        </Tile>

        {/* Data & Privacy Controls */}
        <Tile tone="parchment" className="p-4">
          <h3 className="text-[16px] font-semibold text-[var(--ink)] mb-3">🔒 Data & Account</h3>

          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={handleExport}
              className="text-left text-[14px] font-semibold text-[var(--primary)] py-2 border-b border-[var(--hairline)] hover:underline"
            >
              Export All My Data (JSON)
            </button>

            {exportJson && (
              <pre className="mt-2 max-h-40 overflow-y-auto rounded-[var(--r-sm)] bg-[var(--canvas)] p-2 text-[11px] text-[var(--ink)]">
                {exportJson}
              </pre>
            )}

            <button
              type="button"
              onClick={handleLogout}
              className="text-left text-[14px] font-semibold text-[var(--ink-muted-80)] py-2 border-b border-[var(--hairline)] hover:underline"
            >
              Sign Out
            </button>

            <button
              type="button"
              onClick={handleDeleteAccount}
              className="text-left text-[14px] font-semibold text-[var(--danger)] py-2 hover:underline"
            >
              Delete Account Permanently
            </button>
          </div>
        </Tile>

        <Footer />
      </main>

      <BottomNav current="me" />
    </div>
  );
}
