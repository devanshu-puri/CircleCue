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
import { getCards, createCard, deleteCard } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export default function ExamCardPage() {
  useRequireAuth();
  const [examSets, setExamSets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [examDate, setExamDate] = useState(new Date().toISOString().split("T")[0]);
  const [subject, setSubject] = useState("");
  const [startTime, setStartTime] = useState("10:00");
  const [endTime, setEndTime] = useState("13:00");
  const [preBuffer, setPreBuffer] = useState(30);
  const [postBuffer, setPostBuffer] = useState(15);
  const [saving, setSaving] = useState(false);

  async function loadExams() {
    setLoading(true);
    try {
      const res = await getCards("exam");
      setExamSets(res.exam_sets || []);
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadExams();
  }, []);

  async function handleCreateExam(e: React.FormEvent) {
    e.preventDefault();
    if (!subject || !examDate) return;
    setSaving(true);
    try {
      const payload = {
        date: examDate,
        items: [
          {
            type: "exam",
            subject,
            start_local: startTime,
            end_local: endTime,
            calls_ok: false,
          },
        ],
        pre_buffer_min: Number(preBuffer),
        post_buffer_min: Number(postBuffer),
        keep_schedule: false,
      };
      await createCard("exam", payload);
      setModalOpen(false);
      setSubject("");
      loadExams();
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteExam(id: string, version: number = 1) {
    await deleteCard("exam", id, version);
    loadExams();
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] pb-28">
      <GlobalNav />
      <SubNavFrosted
        title="Exams"
        action={
          <Link href="/me">
            <span className="text-[14px] font-semibold text-[var(--primary)]">← Back</span>
          </Link>
        }
      />

      <main className="mx-auto flex max-w-[390px] flex-col gap-4 px-4 py-5">
        <div className="flex items-center justify-between">
          <p className="text-[13px] text-[var(--ink-muted-80)]">
            Configure exam sets with automatic silence buffers.
          </p>
          <PillButton variant="primary" onClick={() => setModalOpen(true)} className="!py-1 !px-3 text-[14px]">
            + Add Exam
          </PillButton>
        </div>

        <Tile tone="light" className="p-4">
          <h2 className="text-[16px] font-semibold text-[var(--ink)] mb-3">
            Configured Exam Sessions ({examSets.length})
          </h2>

          {loading ? (
            <SkeletonBlock className="h-32 w-full" />
          ) : examSets.length === 0 ? (
            <div className="py-8 text-center text-[14px] text-[var(--ink-muted-48)]">
              No exam sets configured.
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {examSets.map((set) => (
                <div
                  key={set._id}
                  className="flex items-center justify-between rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3"
                >
                  <div>
                    <p className="text-[15px] font-semibold text-[var(--ink)]">
                      {set.items?.[0]?.subject || "Exam"}
                    </p>
                    <p className="text-[13px] text-[var(--ink-muted-80)]">
                      Date: {set.date} · {set.items?.[0]?.start_local} – {set.items?.[0]?.end_local}
                    </p>
                    <p className="text-[11px] text-[var(--ink-muted-48)]">
                      Buffers: -{set.pre_buffer_min}m / +{set.post_buffer_min}m
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteExam(set._id, set.version || 1)}
                    className="text-[13px] font-semibold text-[var(--danger)] hover:underline"
                  >
                    Finish
                  </button>
                </div>
              ))}
            </div>
          )}
        </Tile>

        <Footer />
      </main>

      {/* Add Exam Modal */}
      <BottomSheet isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Schedule Exam">
        <form onSubmit={handleCreateExam} className="flex flex-col gap-4">
          <InputField
            label="Subject / Exam Title"
            placeholder="e.g. Physics Final"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            required
          />

          <InputField
            label="Date"
            type="date"
            value={examDate}
            onChange={(e) => setExamDate(e.target.value)}
            required
          />

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

          <div className="grid grid-cols-2 gap-3">
            <InputField
              label="Pre-buffer (min)"
              type="number"
              value={preBuffer}
              onChange={(e) => setPreBuffer(Number(e.target.value))}
            />
            <InputField
              label="Post-buffer (min)"
              type="number"
              value={postBuffer}
              onChange={(e) => setPostBuffer(Number(e.target.value))}
            />
          </div>

          <PillButton type="submit" variant="primary" disabled={saving} className="w-full mt-2">
            {saving ? "Saving exam..." : "Save Exam"}
          </PillButton>
        </form>
      </BottomSheet>

      <BottomNav current="me" />
    </div>
  );
}
