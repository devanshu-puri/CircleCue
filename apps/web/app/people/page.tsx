"use client";

import React, { useEffect, useState } from "react";
import {
  GlobalNav,
  SubNavFrosted,
  Tile,
  PillButton,
  AvatarCircle,
  BottomSheet,
  ProvenanceCapsule,
  SearchInput,
  SkeletonBlock,
  BottomNav,
  Footer,
} from "@/components/ui";
import {
  getConnections,
  lookupUser,
  sendConnectionRequest,
  respondToConnection,
  removeConnection,
  getViewerState,
  getViewerTimeline,
  type Connection,
  type UserProfile,
  type ViewerState,
  type ViewerTimeline,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export default function PeoplePage() {
  useRequireAuth();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Detail Sheet State
  const [selectedUser, setSelectedUser] = useState<Connection["other_user"] | null>(null);
  const [viewerState, setViewerState] = useState<ViewerState | null>(null);
  const [viewerTimeline, setViewerTimeline] = useState<ViewerTimeline | null>(null);
  const [loadingState, setLoadingState] = useState(false);

  // Add Person Sheet State
  const [addOpen, setAddOpen] = useState(false);
  const [searchCode, setSearchCode] = useState("");
  const [lookupResult, setLookupResult] = useState<UserProfile | null>(null);
  const [searching, setSearching] = useState(false);
  const [requestSent, setRequestSent] = useState(false);

  async function loadConnections() {
    setLoading(true);
    try {
      const data = await getConnections();
      setConnections(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load connections");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadConnections();
  }, []);

  async function handleSelectConnection(conn: Connection) {
    if (!conn.other_user) return;
    setSelectedUser(conn.other_user);
    setViewerState(null);
    setViewerTimeline(null);
    setLoadingState(true);
    try {
      const st = await getViewerState(conn.other_user.id);
      setViewerState(st);
      if (st?.card_access?.schedule && st.card_access.schedule !== "none") {
        setViewerTimeline(await getViewerTimeline(conn.other_user.id));
      }
    } catch {
      // Ignored
    } finally {
      setLoadingState(false);
    }
  }

  async function handleLookup() {
    if (!searchCode.trim()) return;
    setSearching(true);
    setLookupResult(null);
    setRequestSent(false);
    try {
      const res = await lookupUser(searchCode.trim().toUpperCase());
      setLookupResult(res);
    } catch (err: any) {
      setError(err.message || "User not found");
    } finally {
      setSearching(false);
    }
  }

  async function handleSendRequest() {
    if (!lookupResult) return;
    try {
      await sendConnectionRequest(lookupResult.user_code);
      setRequestSent(true);
      setTimeout(() => {
        setAddOpen(false);
        setSearchCode("");
        setLookupResult(null);
        setRequestSent(false);
        loadConnections();
      }, 1200);
    } catch (err: any) {
      setError(err.message || "Failed to send request");
    }
  }

  async function handleRespond(id: string, accept: boolean) {
    try {
      await respondToConnection(id, accept);
      loadConnections();
    } catch (err: any) {
      setError(err.message || "Action failed");
    }
  }

  async function handleRemove(id: string) {
    try {
      await removeConnection(id);
      setSelectedUser(null);
      loadConnections();
    } catch (err: any) {
      setError(err.message || "Failed to remove connection");
    }
  }

  const activeConnections = connections.filter((c) => c.status === "active");
  const pendingConnections = connections.filter((c) => c.status === "pending");

  return (
    <div className="min-h-screen bg-[var(--canvas)] pb-28">
      <GlobalNav />
      <SubNavFrosted
        title="People"
        action={
          <PillButton variant="ghost" onClick={() => setAddOpen(true)} className="!py-1 !px-3 text-[14px]">
            + Add Person
          </PillButton>
        }
      />

      <main className="mx-auto flex max-w-[390px] flex-col gap-4 px-4 py-5">
        {error && <p className="text-[13px] text-[var(--danger)]">{error}</p>}

        {/* Pending Requests */}
        {pendingConnections.length > 0 && (
          <Tile tone="parchment" className="p-4">
            <h2 className="text-[14px] font-semibold uppercase tracking-wider text-[var(--ink-muted-80)] mb-3">
              Pending Requests ({pendingConnections.length})
            </h2>
            <div className="flex flex-col gap-3">
              {pendingConnections.map((conn) => (
                <div
                  key={conn.id || conn._id}
                  className="flex items-center justify-between rounded-[var(--r-md)] bg-[var(--canvas)] p-3 border border-[var(--hairline)]"
                >
                  <div className="flex items-center gap-3">
                    <AvatarCircle name={conn.other_user?.name || "User"} size={36} />
                    <div>
                      <p className="text-[15px] font-semibold text-[var(--ink)]">{conn.other_user?.name}</p>
                      <p className="text-[12px] text-[var(--ink-muted-48)]">{conn.other_user?.user_code}</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleRespond(conn.id || conn._id || "", true)}
                      className="rounded-[var(--r-pill)] bg-[var(--primary)] px-3 py-1 text-[13px] font-semibold text-[var(--on-primary)] active:scale-[0.95]"
                    >
                      Accept
                    </button>
                    <button
                      onClick={() => handleRespond(conn.id || conn._id || "", false)}
                      className="rounded-[var(--r-pill)] border border-[var(--hairline)] bg-[var(--canvas)] px-3 py-1 text-[13px] text-[var(--ink-muted-80)] active:scale-[0.95]"
                    >
                      Decline
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </Tile>
        )}

        {/* Active Connections List */}
        <Tile tone="light" className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[17px] font-semibold text-[var(--ink)]">
              Your Circle ({activeConnections.length})
            </h2>
          </div>

          {loading ? (
            <div className="flex flex-col gap-3">
              <SkeletonBlock className="h-16 w-full" />
              <SkeletonBlock className="h-16 w-full" />
            </div>
          ) : activeConnections.length === 0 ? (
            <div className="py-8 text-center text-[14px] text-[var(--ink-muted-48)]">
              <p>No connections yet.</p>
              <p className="mt-1">Add trusted friends by their universal code.</p>
              <PillButton variant="primary" onClick={() => setAddOpen(true)} className="mt-4">
                Add your first connection
              </PillButton>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {activeConnections.map((conn) => (
                <div
                  key={conn.id || conn._id}
                  onClick={() => handleSelectConnection(conn)}
                  className="flex items-center justify-between rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3 cursor-pointer transition-transform active:scale-[0.98]"
                >
                  <div className="flex items-center gap-3">
                    <AvatarCircle name={conn.other_user?.name || "User"} size={40} />
                    <div>
                      <p className="text-[16px] font-semibold text-[var(--ink)]">{conn.other_user?.name}</p>
                      <p className="text-[12px] text-[var(--ink-muted-48)]">{conn.other_user?.user_code}</p>
                    </div>
                  </div>
                  <span className="text-[13px] font-semibold text-[var(--primary)]">View →</span>
                </div>
              ))}
            </div>
          )}
        </Tile>

        <Footer />
      </main>

      {/* Viewer State Detail Bottom Sheet */}
      <BottomSheet
        isOpen={selectedUser !== null}
        onClose={() => setSelectedUser(null)}
        title={selectedUser?.name || "Person"}
      >
        {loadingState ? (
          <SkeletonBlock className="h-40 w-full" />
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3 pb-3 border-b border-[var(--hairline)]">
              <AvatarCircle name={selectedUser?.name || "User"} size={48} />
              <div>
                <p className="text-[18px] font-semibold text-[var(--ink)]">{selectedUser?.name}</p>
                <p className="text-[13px] text-[var(--ink-muted-48)]">Code: {selectedUser?.user_code}</p>
              </div>
            </div>

            {/* Availability Tile */}
            <Tile
              tone={viewerState?.reachability?.calls === "no" ? "dark" : "light"}
              className="p-4"
            >
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-semibold uppercase tracking-wider opacity-75">
                  Availability
                </span>
                {viewerState?.activity?.provenance && (
                  <ProvenanceCapsule>
                    {viewerState.activity.provenance.source === "user_shared"
                      ? "User shared"
                      : "System inferred"}
                  </ProvenanceCapsule>
                )}
              </div>
              <h3 className="mt-2 text-[22px] font-semibold">
                {viewerState?.sharing_paused
                  ? "Sharing paused"
                  : viewerState?.activity?.label || viewerState?.activity?.type || (viewerState?.reachability ? (viewerState.reachability.calls === "no" ? "Busy" : "Available") : "Status not shared")}
              </h3>
              <p className="mt-1 text-[14px] opacity-85">
                {viewerState?.reachability
                  ? `Calls: ${viewerState.reachability.calls || "ok"} · Messages: ${viewerState.reachability.messages || "ok"}${viewerState.reachability.until ? ` · Until ${new Date(viewerState.reachability.until).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}` : ""}`
                  : viewerState?.sharing_paused ? "No details are shared while sharing is paused." : "Live availability hasn’t been shared with you."}
              </p>
            </Tile>

            {/* Specific context cards */}
            <div className="grid grid-cols-2 gap-2 text-[13px]">
              <div className="rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3">
                <p className="font-semibold">Phone</p>
                <p className="text-[var(--ink-muted-80)]">
                  {viewerState?.phone
                    ? `${viewerState.phone.mode === "silent" ? "On Silent" : viewerState.phone.mode === "dnd" ? "On Do Not Disturb" : "On ring"}${viewerState.phone.battery_pct != null ? ` · ${viewerState.phone.battery_pct}%` : viewerState.phone.battery_bucket ? ` · Battery ${viewerState.phone.battery_bucket}` : ""}`
                    : "Not shared"}
                </p>
              </div>
              <div className="rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3">
                <p className="font-semibold">Travel</p>
                <p className="text-[var(--ink-muted-80)]">
                  {viewerState?.travel?.destination || (viewerState?.travel ? "Travelling" : viewerState?.current_place || (["status", "details"].includes(viewerState?.card_access?.travel || "none") ? "No active journey" : "Not shared"))}
                </p>
              </div>
            </div>

            {viewerState?.messages && viewerState.messages.length > 0 && (
              <Tile tone="parchment" className="p-4">
                <h3 className="mb-2 text-[15px] font-semibold text-[var(--ink)]">Dropped messages</h3>
                <div className="flex flex-col gap-2">
                  {viewerState.messages.map((message) => (
                    <div key={message.id} className="rounded-[var(--r-sm)] bg-[var(--canvas)] p-3">
                      <p className="text-[14px] text-[var(--ink)]">{message.text || "Shared a note with you."}</p>
                      {message.promise_at && <p className="mt-1 text-[12px] text-[var(--ink-muted-80)]">Promise by {new Date(message.promise_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</p>}
                      <p className="mt-1 text-[11px] text-[var(--ink-muted-48)]">Expires {new Date(message.expires_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</p>
                    </div>
                  ))}
                </div>
              </Tile>
            )}

            {viewerState?.card_access?.schedule && viewerState.card_access.schedule !== "none" && (
              <Tile tone="parchment" className="p-4">
                <h3 className="mb-2 text-[15px] font-semibold text-[var(--ink)]">Today’s schedule</h3>
                {viewerTimeline?.sharing_paused ? (
                  <p className="text-[14px] text-[var(--ink-muted-80)]">Sharing paused.</p>
                ) : viewerTimeline?.segments.length ? (
                  <div className="flex flex-col gap-2">
                    {viewerTimeline.segments.map((segment) => (
                      <div key={`${segment.start}-${segment.end}`} className="flex justify-between gap-3 rounded-[var(--r-sm)] bg-[var(--canvas)] p-2 text-[13px]">
                        <span className="font-semibold text-[var(--ink)]">{segment.label}</span>
                        <span className="shrink-0 text-[var(--ink-muted-80)]">{new Date(segment.start).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}–{new Date(segment.end).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[14px] text-[var(--ink-muted-80)]">No scheduled slots today.</p>
                )}
              </Tile>
            )}

            {/* Action buttons */}
            <div className="flex gap-2 pt-2">
              <a href="tel:" className="flex-1">
                <PillButton variant="primary" className="w-full">
                  Call
                </PillButton>
              </a>
              <a href="sms:" className="flex-1">
                <PillButton variant="ghost" className="w-full">
                  Message
                </PillButton>
              </a>
            </div>
          </div>
        )}
      </BottomSheet>

      {/* Add Person Bottom Sheet */}
      <BottomSheet isOpen={addOpen} onClose={() => setAddOpen(false)} title="Add Person">
        <div className="flex flex-col gap-4">
          <p className="text-[13px] text-[var(--ink-muted-80)]">
            Enter their universal CircleCue code (e.g. ARJUN-7842) to connect.
          </p>

          <div className="flex gap-2">
            <input
              type="text"
              placeholder="NAME-XXXX"
              value={searchCode}
              onChange={(e) => setSearchCode(e.target.value)}
              className="flex-1 rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] px-3 py-2 text-[16px] uppercase font-mono tracking-wider text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-focus)]"
            />
            <PillButton variant="primary" onClick={handleLookup} disabled={searching || !searchCode.trim()}>
              {searching ? "..." : "Lookup"}
            </PillButton>
          </div>

          {lookupResult && (
            <div className="flex flex-col gap-3 rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-4 mt-2">
              <div className="flex items-center gap-3">
                <AvatarCircle name={lookupResult.name} size={40} />
                <div>
                  <p className="text-[16px] font-semibold text-[var(--ink)]">{lookupResult.name}</p>
                  <p className="text-[12px] text-[var(--ink-muted-48)]">{lookupResult.user_code}</p>
                </div>
              </div>

              {requestSent ? (
                <p className="text-center font-semibold text-[var(--primary)] text-[14px]">
                  ✓ Connection request sent!
                </p>
              ) : (
                <PillButton variant="primary" onClick={handleSendRequest} className="w-full mt-2">
                  Send Connection Request
                </PillButton>
              )}
            </div>
          )}
        </div>
      </BottomSheet>

      <BottomNav current="people" />
    </div>
  );
}
