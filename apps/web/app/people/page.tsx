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
  type Connection,
  type UserProfile,
  type ViewerState,
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
    setLoadingState(true);
    try {
      const st = await getViewerState(conn.other_user.id);
      setViewerState(st);
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
                  key={conn._id}
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
                      onClick={() => handleRespond(conn._id, true)}
                      className="rounded-[var(--r-pill)] bg-[var(--primary)] px-3 py-1 text-[13px] font-semibold text-[var(--on-primary)] active:scale-[0.95]"
                    >
                      Accept
                    </button>
                    <button
                      onClick={() => handleRespond(conn._id, false)}
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
                  key={conn._id}
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
                {viewerState?.activity?.label || viewerState?.activity?.type || "Available"}
              </h3>
              <p className="mt-1 text-[14px] opacity-85">
                {viewerState?.reachability?.reason ||
                  (viewerState?.reachability?.calls === "no" ? "Calls: not now" : "Calls: ok")}
              </p>
            </Tile>

            {/* Specific context cards */}
            <div className="grid grid-cols-2 gap-2 text-[13px]">
              <div className="rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3">
                <p className="font-semibold">Phone</p>
                <p className="text-[var(--ink-muted-80)]">
                  {viewerState?.phone?.mode === "silent"
                    ? "Silent"
                    : viewerState?.phone?.battery_pct
                    ? `${viewerState.phone.battery_pct}%`
                    : "Normal"}
                </p>
              </div>
              <div className="rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3">
                <p className="font-semibold">Travel</p>
                <p className="text-[var(--ink-muted-80)]">
                  {viewerState?.travel ? viewerState.travel.destination || "Travelling" : "At home"}
                </p>
              </div>
            </div>

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
