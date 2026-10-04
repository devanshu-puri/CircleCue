"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Chip,
  Footer,
  GlobalNav,
  PillButton,
  SearchInput,
  SubNavFrosted,
  Tile,
  UtilityCard,
  BottomSheet,
  ProvenanceCapsule,
  SkeletonBlock,
  BottomNav,
} from "@/components/ui";
import {
  getMyState,
  getNotifications,
  subscribeToNotifications,
  parseText,
  confirmDraft,
  getCards,
  updateCard,
  type NotificationItem,
  type ViewerState,
  type ParseResult,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

function resolveStatus(state: ViewerState | null) {
  if (!state) {
    return {
      title: "Shared status",
      detail: "Loading live context...",
      tone: "light" as const,
      chips: ["Available"],
    };
  }

  const reachability = state.reachability ?? {};
  const calls = reachability.calls ?? "ok";
  const isBusy = calls === "no" || calls === "prefer_not";

  const activity = state.activity as Record<string, any> | null | undefined;
  const title = readableText(activity?.label ?? activity?.type ?? (isBusy ? "Busy" : "Available"));

  let detail = readableText(reachability.reason || (calls === "no" ? "Calls: not now" : (calls === "prefer_not" ? "Calls: prefer not" : "Calls: ok")));
  if (reachability.free_in_min) {
    detail = `${detail} · Free in ~${reachability.free_in_min}m`;
  } else if (reachability.until) {
    detail = `${detail} · until ${new Date(reachability.until).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  }

  const chips = [
    calls === "ok" ? "🟢 Reachable" : "🔴 Busy",
    state.phone?.battery_pct ? `⚡ ${state.phone.battery_pct}%` : "⚡ Phone ok",
    state.travel ? `✈️ ${state.travel.destination || "Travelling"}` : "🏠 At home",
  ];

  return {
    title,
    detail,
    tone: isBusy ? ("dark" as const) : ("light" as const),
    chips,
    provenance: activity?.provenance,
  };
}

function readableText(value: string): string {
  return value
    .replace(/&quot;|&#34;|&#x22;/gi, '"')
    .replace(/&apos;|&#39;|&#x27;/gi, "'")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&nbsp;/gi, " ");
}

export default function HomePage() {
  const { user } = useRequireAuth();
  const [state, setState] = useState<ViewerState | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Quick composer state
  const [composeOpen, setComposeOpen] = useState(false);
  const [composeText, setComposeText] = useState("");
  const [parseLoading, setParseLoading] = useState(false);
  const [parsedDraft, setParsedDraft] = useState<ParseResult | null>(null);
  const [missingAnswers, setMissingAnswers] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);
  const [composeSuccess, setComposeSuccess] = useState(false);
  const [finishingActivity, setFinishingActivity] = useState(false);

  async function loadData() {
    setLoading(true);
    try {
      const [nextState, nextNotifications] = await Promise.all([getMyState(), getNotifications()]);
      setState(nextState);
      setNotifications(nextNotifications);
      setError(null);
    } catch (caught: any) {
      setError(caught.message || "Unable to load state");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();

    const stream = subscribeToNotifications((notification) => {
      setNotifications((current) => [notification, ...current]);
    });

    return () => {
      stream.close();
    };
  }, []);

  const currentStatus = useMemo(() => resolveStatus(state), [state]);

  async function handleFinishActivity() {
    if (!state?.activity) return;
    setFinishingActivity(true);
    setError(null);
    try {
      const cards = await getCards("live");
      const candidates = (Array.isArray(cards) ? cards : []).filter((card: any) =>
        card.type === state.activity?.type &&
        readableText(card.title || "") === readableText(state.activity?.label || "") &&
        ["ACTIVE", "EXTENDED", "DELAYED", "CHANGED"].includes(card.status)
      );
      const current = candidates.sort((a: any, b: any) =>
        new Date(b.start_at || 0).getTime() - new Date(a.start_at || 0).getTime()
      )[0];
      if (!current) throw new Error("Could not find the active update to finish. Refresh and try again.");
      await updateCard("live", current._id || current.id, {
        status: "COMPLETED",
        version: current.version || 1,
      });
      await loadData();
    } catch (caught: any) {
      setError(caught.message || "Could not finish this update.");
    } finally {
      setFinishingActivity(false);
    }
  }

  async function handleParse() {
    if (!composeText.trim()) return;
    setParseLoading(true);
    setParsedDraft(null);
    setMissingAnswers({});
    try {
      const res = await parseText(composeText.trim());
      setParsedDraft(res);
    } catch (err: any) {
      setError(err.message || "AI parse error");
    } finally {
      setParseLoading(false);
    }
  }

  async function handleConfirm() {
    if (!parsedDraft) return;
    setConfirming(true);
    try {
      const answeredMissing = parsedDraft.missing.filter((missing) =>
        ["destination", "eta", "companion"].includes(missing.field) && missingAnswers[missing.field]?.trim()
      );
      if (answeredMissing.length > 0) {
        const addedDetails = answeredMissing
          .map((missing) => {
            const answer = missingAnswers[missing.field].trim();
            if (missing.field === "destination") return `going to ${answer}`;
            if (missing.field === "companion") return `with ${answer}`;
            const relative = answer.match(/(?:within|in)\s+(\d+)\s*(minutes?|mins?|hours?|hrs?)/i);
            return relative ? `arrive in ${relative[1]} ${relative[2]}` : `arrive at ${answer}`;
          })
          .join(". ");
        const revised = await parseText(`${composeText.trim()}. ${addedDetails}`);
        setParsedDraft(revised);
        setMissingAnswers({});
        setError(null);
        return;
      }
      await confirmDraft(parsedDraft.items, parsedDraft.draft_id);
      setComposeSuccess(true);
      setTimeout(() => {
        setComposeOpen(false);
        setComposeText("");
        setParsedDraft(null);
        setComposeSuccess(false);
        loadData();
      }, 1000);
    } catch (err: any) {
      setError(err.message || "Failed to confirm update");
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] pb-28">
      <GlobalNav alertCount={notifications.filter((n) => !n.read_at).length} />
      <SubNavFrosted
        title="Today"
        action={
          <PillButton variant="ghost" onClick={() => setComposeOpen(true)} className="!py-1 !px-3 text-[14px]">
            + Update
          </PillButton>
        }
      />

      <main className="mx-auto flex max-w-[390px] flex-col gap-4 px-4 py-5">
        {/* Main Status Tile (light = reachable, dark = busy) */}
        <Tile tone={currentStatus.tone} className="p-5 transition-colors">
          <div className="flex items-center justify-between">
            <p className="text-[12px] font-normal uppercase leading-[1.0] tracking-[0.2em] text-[var(--body-muted)]">
              {loading ? "Loading shared status..." : "Shared status"}
            </p>
            {currentStatus.provenance && (
              <ProvenanceCapsule>
                {currentStatus.provenance.source === "system_inferred"
                  ? "System inferred"
                  : currentStatus.provenance.source === "ai_parsed_user_confirmed"
                  ? "AI verified"
                  : "User shared"}
              </ProvenanceCapsule>
            )}
          </div>

          <h1
            className={`mt-3 font-[family-name:var(--font-display)] text-[34px] font-semibold leading-[1.1] tracking-0 ${
              currentStatus.tone === "dark" ? "text-[var(--body-on-dark)]" : "text-[var(--ink)]"
            }`}
          >
            {currentStatus.title}
          </h1>
          <p
            className={`mt-2 text-[17px] leading-[1.47] tracking-[-0.374px] ${
              currentStatus.tone === "dark" ? "text-[var(--body-muted)]" : "text-[var(--ink-muted-80)]"
            }`}
          >
            {error || currentStatus.detail}
          </p>

          <div className="mt-5 flex gap-2">
            <PillButton variant="primary" onClick={() => setComposeOpen(true)}>
              Share Update
            </PillButton>
            <Link href="/me">
              <PillButton variant="ghost">Manage Cards</PillButton>
            </Link>
          </div>
          {state?.activity?.layer === 2 && (
            <PillButton variant="ghost" onClick={handleFinishActivity} disabled={finishingActivity} className="mt-3 w-full">
              {finishingActivity ? "Updating status…" : "I’m free now · finish this update"}
            </PillButton>
          )}
        </Tile>

        {/* Quick Compose Input trigger */}
        <Tile id="today-summary" tone="parchment" className="p-4">
          <div onClick={() => setComposeOpen(true)} className="cursor-pointer">
            <SearchInput placeholder="What’s happening? (e.g. lab till 4, no calls)" />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {currentStatus.chips.map((chip) => (
              <Chip key={chip} selected={true}>
                {chip}
              </Chip>
            ))}
          </div>
        </Tile>

        {/* 4 Cards Quick Grid */}
        <Tile tone="light" className="p-4">
          <div className="grid grid-cols-2 gap-3">
            <Link href="/me/schedule">
              <UtilityCard
                title="Schedule"
                subtitle={state?.activity ? "Active slot" : "Routine"}
                action={<span className="text-[12px] font-semibold text-[var(--primary)]">Edit</span>}
              />
            </Link>
            <Link href="/me/exam">
              <UtilityCard
                title="Exams"
                subtitle={state?.exam ? `${state.exam.exams_today || 1} today` : "No exam"}
                action={<span className="text-[12px] font-semibold text-[var(--primary)]">View</span>}
              />
            </Link>
            <Link href="/me/travel">
              <UtilityCard
                title="Travel"
                subtitle={state?.travel ? state.travel.destination || "On route" : "At home"}
                action={<span className="text-[12px] font-semibold text-[var(--primary)]">ETA</span>}
              />
            </Link>
            <Link href="/me#phone-card">
              <UtilityCard
                title="Phone"
                subtitle={state?.phone ? (state.phone.mode === "silent" ? "Silent" : "Healthy") : "Healthy"}
                action={<span className="text-[12px] font-semibold text-[var(--primary)]">Status</span>}
              />
            </Link>
          </div>
        </Tile>

        {/* Today Timeline & Alerts */}
        <Tile tone="parchment" className="p-4">
          <div className="space-y-4">
            <p className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px] text-[var(--ink)]">
              Today
            </p>
            <div className="border-l-2 border-[var(--hairline)] pl-3">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-[14px] font-semibold text-[var(--ink)]">
                    {state?.next_boundary_at
                      ? new Date(state.next_boundary_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
                      : "Next boundary"}
                  </p>
                  <p className="text-[13px] text-[var(--ink-muted-48)]">
                    {state?.activity ? `Next state boundary · ${state.activity.label}` : "Routine baseline active"}
                  </p>
                </div>
                <span className="text-[11px] uppercase tracking-[0.12em] text-[var(--ink-muted-48)]">
                  {state?.activity ? "Active" : "Idle"}
                </span>
              </div>
            </div>

            <div className="border-l-2 border-[var(--hairline)] pl-3">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-[14px] font-semibold text-[var(--ink)]">Alerts</p>
                  <p className="text-[13px] text-[var(--ink-muted-48)]">
                    {notifications.length ? `${notifications.length} recent alerts` : "No new alerts"}
                  </p>
                </div>
                <Link href="/permissions" className="text-[12px] font-semibold text-[var(--primary)]">
                  Open
                </Link>
              </div>
            </div>
          </div>
        </Tile>

        <Footer />
      </main>

      {/* AI Quick Compose Bottom Sheet */}
      <BottomSheet
        isOpen={composeOpen}
        onClose={() => {
          setComposeOpen(false);
          setParsedDraft(null);
        }}
        title="Quick Update"
      >
        <div className="flex flex-col gap-4">
          {error && <p role="alert" className="text-[14px] text-[var(--danger)]">{error}</p>}
          <p className="text-[13px] text-[var(--ink-muted-80)]">
            Tell CircleCue in plain words (e.g. “studying till 8, no calls” or “leaving for Delhi tomorrow 8am”).
          </p>

          <textarea
            rows={3}
            value={composeText}
            onChange={(e) => setComposeText(e.target.value)}
            placeholder="What's happening?"
            className="w-full rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3 text-[17px] text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-focus)]"
          />

          {!parsedDraft && (
            <PillButton variant="primary" onClick={handleParse} disabled={parseLoading || !composeText.trim()}>
              {parseLoading ? "Parsing with AI..." : "Parse Update"}
            </PillButton>
          )}

          {parseLoading && <SkeletonBlock className="h-28 w-full" />}

          {parsedDraft && (
            <div className="flex flex-col gap-3 rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-4">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-semibold uppercase tracking-wider text-[var(--ink-muted-80)]">
                  Draft Preview
                </span>
                <ProvenanceCapsule>AI parsed · confirm to save</ProvenanceCapsule>
              </div>

              <div className="text-[15px] font-medium text-[var(--ink)]">
                Intent: <span className="font-semibold text-[var(--primary)]">{parsedDraft.intent}</span>
              </div>

              {parsedDraft.items.map((item, idx) => (
                <div key={idx} className="rounded-[var(--r-sm)] bg-[var(--canvas)] p-3 text-[14px]">
                  <p className="font-semibold">{item.title || item.kind}</p>
                  {item.availability && (
                    <p className="text-[12px] text-[var(--ink-muted-80)]">
                      Calls: {item.availability.calls} · Messages: {item.availability.messages}
                    </p>
                  )}
                  {item.destination && (
                    <p className="text-[12px] text-[var(--ink-muted-80)]">Destination: {item.destination}</p>
                  )}
                </div>
              ))}

              {parsedDraft.intent === "unknown" && parsedDraft.items.length === 0 ? (
                <p className="rounded-[var(--r-sm)] bg-[var(--canvas)] p-3 text-[14px] text-[var(--ink-muted-80)]">
                  I couldn’t identify an update to save. Try describing an activity, travel plan, phone status, or message.
                </p>
              ) : parsedDraft.missing.length > 0 && (
                <div className="flex flex-col gap-2 mt-2">
                  <p className="text-[13px] font-semibold text-[var(--ink)]">Missing details:</p>
                  {parsedDraft.missing.map((m) => (
                    <div key={m.field} className="flex flex-col gap-1">
                      <span className="text-[12px] text-[var(--ink-muted-80)]">{m.question}</span>
                      <input
                        type="text"
                        placeholder="Provide details..."
                        value={missingAnswers[m.field] || ""}
                        onChange={(e) =>
                          setMissingAnswers({ ...missingAnswers, [m.field]: e.target.value })
                        }
                        className="rounded-[var(--r-sm)] border border-[var(--hairline)] bg-[var(--canvas)] px-2 py-1 text-[14px]"
                      />
                    </div>
                  ))}
                </div>
              )}

              {composeSuccess ? (
                <p className="text-center font-semibold text-[var(--primary)]">✓ Saved and active!</p>
              ) : (
                <div className="flex gap-2 mt-2">
                  <PillButton
                    variant="primary"
                    onClick={handleConfirm}
                    disabled={confirming || (parsedDraft.intent === "unknown" && parsedDraft.items.length === 0) || (parsedDraft.missing.length > 0 && parsedDraft.missing.some((missing) => ["destination", "eta", "companion"].includes(missing.field) && !missingAnswers[missing.field]?.trim()))}
                    className="flex-1"
                  >
                    {confirming ? "Updating..." : parsedDraft.missing.length > 0 ? "Update Draft & Review" : "Confirm & Apply"}
                  </PillButton>
                  <PillButton
                    variant="ghost"
                    onClick={() => {
                      setParsedDraft(null);
                    }}
                  >
                    Reset
                  </PillButton>
                </div>
              )}
            </div>
          )}
        </div>
      </BottomSheet>

      <BottomNav current="home" />
    </div>
  );
}
