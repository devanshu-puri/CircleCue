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
import {
  getCards,
  createCard,
  deleteCard,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export default function ScheduleCardPage() {
  useRequireAuth();
  const [templates, setTemplates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Form State
  const [modalOpen, setModalOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4]); // Mon-Fri
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("11:00");
  const [callsOk, setCallsOk] = useState(false);
  const [saving, setSaving] = useState(false);

  const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  async function loadSchedule() {
    setLoading(true);
    try {
      const res = await getCards("schedule");
      setTemplates(res.templates || []);
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSchedule();
  }, []);

  function toggleDay(d: number) {
    if (days.includes(d)) {
      setDays(days.filter((x) => x !== d));
    } else {
      setDays([...days, d].sort());
    }
  }

  async function handleAddSlot(e: React.FormEvent) {
    e.preventDefault();
    if (!title || days.length === 0) return;
    setSaving(true);
    try {
      const newTemplate = {
        kind: "SCHEDULE_SLOT",
        title,
        activity_type: "LECTURE",
        days,
        start_local: startTime,
        end_local: endTime,
        week_pattern: "every",
        availability: {
          calls: callsOk ? "ok" : "no",
          messages: "ok",
        },
        visibility: { mode: "inherit" },
      };
      await createCard("schedule", {
        templates: [...templates, newTemplate],
      });
      setModalOpen(false);
      setTitle("");
      loadSchedule();
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteSlot(idx: number) {
    const nextTemplates = templates.filter((_, i) => i !== idx);
    await createCard("schedule", { templates: nextTemplates });
    loadSchedule();
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] pb-28">
      <GlobalNav />
      <SubNavFrosted
        title="Schedule"
        action={
          <Link href="/me">
            <span className="text-[14px] font-semibold text-[var(--primary)]">← Back</span>
          </Link>
        }
      />

      <main className="mx-auto flex max-w-[390px] flex-col gap-4 px-4 py-5">
        <div className="flex items-center justify-between">
          <p className="text-[13px] text-[var(--ink-muted-80)]">
            Define recurring lecture and study time blocks.
          </p>
          <PillButton variant="primary" onClick={() => setModalOpen(true)} className="!py-1 !px-3 text-[14px]">
            + Add Slot
          </PillButton>
        </div>

        <Tile tone="light" className="p-4">
          <h2 className="text-[16px] font-semibold text-[var(--ink)] mb-3">
            Active Schedule Slots ({templates.length})
          </h2>

          {loading ? (
            <SkeletonBlock className="h-32 w-full" />
          ) : templates.length === 0 ? (
            <div className="py-8 text-center text-[14px] text-[var(--ink-muted-48)]">
              No schedule slots configured yet.
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {templates.map((t, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3"
                >
                  <div>
                    <p className="text-[15px] font-semibold text-[var(--ink)]">{t.title}</p>
                    <p className="text-[13px] text-[var(--ink-muted-80)]">
                      {t.days?.map((d: number) => WEEKDAYS[d]).join(", ")} · {t.start_local} – {t.end_local}
                    </p>
                    <p className="text-[11px] text-[var(--ink-muted-48)]">
                      Calls: {t.availability?.calls || "no"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteSlot(idx)}
                    className="text-[13px] font-semibold text-[var(--danger)] hover:underline"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </Tile>

        <Footer />
      </main>

      {/* Add Slot Bottom Sheet */}
      <BottomSheet isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Add Schedule Slot">
        <form onSubmit={handleAddSlot} className="flex flex-col gap-4">
          <InputField
            label="Title / Subject"
            placeholder="e.g. Algorithms Lecture"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />

          <div>
            <label className="text-[14px] text-[var(--ink-muted-80)] block mb-2">Days of Week</label>
            <div className="flex flex-wrap gap-1.5">
              {WEEKDAYS.map((name, idx) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => toggleDay(idx)}
                  className={`rounded-[var(--r-pill)] px-3 py-1 text-[13px] font-medium border ${
                    days.includes(idx)
                      ? "bg-[var(--primary)] text-[var(--on-primary)] border-[var(--primary)]"
                      : "bg-[var(--canvas)] text-[var(--ink-muted-80)] border-[var(--hairline)]"
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <InputField
              label="Start time"
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              required
            />
            <InputField
              label="End time"
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              required
            />
          </div>

          <div className="flex items-center justify-between py-2 border-t border-[var(--hairline)]">
            <span className="text-[14px] text-[var(--ink)]">Calls ok during slot?</span>
            <input
              type="checkbox"
              checked={callsOk}
              onChange={(e) => setCallsOk(e.target.checked)}
              className="h-5 w-5"
            />
          </div>

          <PillButton type="submit" variant="primary" disabled={saving} className="w-full mt-2">
            {saving ? "Saving slot..." : "Save Schedule Slot"}
          </PillButton>
        </form>
      </BottomSheet>

      <BottomNav current="me" />
    </div>
  );
}
