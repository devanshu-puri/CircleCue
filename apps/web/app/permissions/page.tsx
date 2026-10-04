"use client";

import React, { useEffect, useState } from "react";
import {
  GlobalNav,
  SubNavFrosted,
  Tile,
  PillButton,
  SegmentedControl,
  Switch,
  BottomSheet,
  BottomNav,
  Footer,
  SkeletonBlock,
  AvatarCircle,
} from "@/components/ui";
import {
  getNotifications,
  markNotificationRead,
  getConnections,
  getGrants,
  updateGrant,
  type NotificationItem,
  type Connection,
  type Grant,
  type AccessLevel,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export default function PermissionsAndAlertsPage() {
  useRequireAuth();
  const [activeTab, setActiveTab] = useState<"alerts" | "permissions">("alerts");
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [loading, setLoading] = useState(true);

  // Grant editor sheet state
  const [selectedConn, setSelectedConn] = useState<Connection | null>(null);
  const [editingGrant, setEditingGrant] = useState<Grant | null>(null);
  const [savingGrant, setSavingGrant] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  async function loadData() {
    setLoading(true);
    try {
      const [notifs, conns, grs] = await Promise.all([
        getNotifications(),
        getConnections(),
        getGrants(),
      ]);
      setNotifications(notifs);
      setConnections(conns.filter((c) => c.status === "active"));
      setGrants(grs);
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleMarkRead(id: string) {
    await markNotificationRead(id);
    setNotifications((prev) =>
      prev.map((n) => (n._id === id ? { ...n, read_at: new Date().toISOString() } : n)),
    );
  }

  function handleOpenGrantEditor(conn: Connection) {
    setSelectedConn(conn);
    const existing = grants.find((g) => g.viewer === conn.other_user?.id);
    if (existing) {
      setEditingGrant({ ...existing });
    } else {
      setEditingGrant({
        owner: "",
        viewer: conn.other_user?.id || "",
        cards: {
          schedule: "none",
          exam: "none",
          live: "none",
          travel: "none",
          phone: "none",
          safety: "none",
          message: "none",
        },
        notify: {
          free_now: false,
          exam: false,
          travel: false,
          battery: false,
          schedule_change: false,
          message: false,
          safety: false,
        },
        important: false,
        reach_through: false,
      });
    }
    setSaveSuccess(false);
  }

  async function handleSaveGrant() {
    if (!selectedConn?.other_user?.id || !editingGrant) return;
    setSavingGrant(true);
    try {
      await updateGrant(selectedConn.other_user.id, editingGrant);
      setSaveSuccess(true);
      setTimeout(() => {
        setSelectedConn(null);
        setEditingGrant(null);
        setSaveSuccess(false);
        loadData();
      }, 1000);
    } finally {
      setSavingGrant(false);
    }
  }

  function updateCardGrant(card: keyof Grant["cards"], level: AccessLevel) {
    if (!editingGrant) return;
    setEditingGrant({
      ...editingGrant,
      cards: {
        ...editingGrant.cards,
        [card]: level,
      },
    });
  }

  function updateNotifyFlag(flag: keyof Grant["notify"], val: boolean) {
    if (!editingGrant) return;
    setEditingGrant({
      ...editingGrant,
      notify: {
        ...editingGrant.notify,
        [flag]: val,
      },
    });
  }

  return (
    <div className="min-h-screen bg-[var(--canvas)] pb-28">
      <GlobalNav alertCount={notifications.filter((n) => !n.read_at).length} />
      <SubNavFrosted
        title={activeTab === "alerts" ? "Alerts" : "Permissions"}
        action={
          <SegmentedControl
            options={[
              { label: "Alerts", value: "alerts" },
              { label: "Permissions", value: "permissions" },
            ]}
            value={activeTab}
            onChange={(val) => setActiveTab(val)}
          />
        }
      />

      <main className="mx-auto flex max-w-[390px] flex-col gap-4 px-4 py-5">
        {loading ? (
          <div className="flex flex-col gap-3">
            <SkeletonBlock className="h-20 w-full" />
            <SkeletonBlock className="h-20 w-full" />
          </div>
        ) : activeTab === "alerts" ? (
          /* TAB 1: ALERTS */
          <Tile tone="light" className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[17px] font-semibold text-[var(--ink)]">Notification Stream</h2>
              <span className="text-[12px] text-[var(--ink-muted-48)]">
                {notifications.length} alerts
              </span>
            </div>

            {notifications.length === 0 ? (
              <div className="py-8 text-center text-[14px] text-[var(--ink-muted-48)]">
                <p>No new alerts.</p>
                <p className="mt-1">When friends share updates or boundaries trigger, they appear here.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {notifications.map((n) => {
                  const isRead = !!n.read_at;
                  return (
                    <div
                      key={n._id}
                      onClick={() => !isRead && handleMarkRead(n._id)}
                      className={`flex flex-col gap-1 rounded-[var(--r-md)] border border-[var(--hairline)] p-3 cursor-pointer transition-colors ${
                        isRead ? "bg-[var(--canvas)] opacity-60" : "bg-[var(--canvas-parchment)]"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--primary)]">
                          {n.kind.replace(/_/g, " ")}
                        </span>
                        <span className="text-[11px] text-[var(--ink-muted-48)]">
                          {new Date(n.created_at).toLocaleTimeString([], {
                            hour: "numeric",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      <p className="text-[14px] text-[var(--ink)] leading-snug">
                        {n.payload_redacted?.text || n.kind}
                      </p>
                      {n.action && (
                        <div className="mt-1">
                          <span className="inline-flex rounded-[var(--r-pill)] border border-[var(--hairline)] bg-[var(--canvas)] px-2 py-0.5 text-[11px] font-medium text-[var(--primary)]">
                            {n.action}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </Tile>
        ) : (
          /* TAB 2: PERMISSIONS */
          <Tile tone="light" className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[17px] font-semibold text-[var(--ink)]">Who Can See What</h2>
            </div>
            <p className="text-[13px] text-[var(--ink-muted-80)] mb-4">
              By default, connections have zero access. Grant permission per-card.
            </p>

            {connections.length === 0 ? (
              <div className="py-8 text-center text-[14px] text-[var(--ink-muted-48)]">
                <p>No active connections to configure.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {connections.map((conn) => {
                  const grant = grants.find((g) => g.viewer === conn.other_user?.id);
                  return (
                    <div
                      key={conn._id}
                      onClick={() => handleOpenGrantEditor(conn)}
                      className="flex items-center justify-between rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-3 cursor-pointer active:scale-[0.98]"
                    >
                      <div className="flex items-center gap-3">
                        <AvatarCircle name={conn.other_user?.name || "User"} size={38} />
                        <div>
                          <p className="text-[15px] font-semibold text-[var(--ink)]">
                            {conn.other_user?.name}
                          </p>
                          <p className="text-[12px] text-[var(--ink-muted-48)]">
                            {grant
                              ? Object.entries(grant.cards)
                                  .filter(([_, lvl]) => lvl !== "none")
                                  .map(([c, l]) => `${c}: ${l}`)
                                  .join(", ") || "No cards granted"
                              : "No grant configured"}
                          </p>
                        </div>
                      </div>
                      <span className="text-[13px] font-semibold text-[var(--primary)]">Edit →</span>
                    </div>
                  );
                })}
              </div>
            )}
          </Tile>
        )}

        <Footer />
      </main>

      {/* Grant Editor Bottom Sheet */}
      <BottomSheet
        isOpen={selectedConn !== null}
        onClose={() => setSelectedConn(null)}
        title={`Grant for ${selectedConn?.other_user?.name || "Person"}`}
      >
        {editingGrant && (
          <div className="flex flex-col gap-5">
            {/* Card Access Levels */}
            <div>
              <h3 className="text-[14px] font-semibold uppercase tracking-wider text-[var(--ink-muted-80)] mb-3">
                Card Access
              </h3>
              <div className="flex flex-col gap-3">
                {(["schedule", "exam", "live", "travel", "phone", "message", "safety"] as const).map(
                  (card) => (
                    <div
                      key={card}
                      className="flex items-center justify-between py-1 border-b border-[var(--hairline)]"
                    >
                      <span className="text-[14px] font-medium capitalize text-[var(--ink)]">
                        {card}
                      </span>
                      <SegmentedControl<AccessLevel>
                        options={[
                          { label: "None", value: "none" },
                          { label: "Status", value: "status" },
                          { label: "Details", value: "details" },
                        ]}
                        value={editingGrant.cards[card] || "none"}
                        onChange={(lvl) => updateCardGrant(card, lvl)}
                      />
                    </div>
                  ),
                )}
              </div>
            </div>

            {/* Notification Toggles */}
            <div>
              <h3 className="text-[14px] font-semibold uppercase tracking-wider text-[var(--ink-muted-80)] mb-3">
                Notify This Person On
              </h3>
              <div className="flex flex-col gap-2">
                <Switch
                  label="When I become free"
                  checked={editingGrant.notify.free_now}
                  onChange={(v) => updateNotifyFlag("free_now", v)}
                />
                <Switch
                  label="Exam updates"
                  checked={editingGrant.notify.exam}
                  onChange={(v) => updateNotifyFlag("exam", v)}
                />
                <Switch
                  label="Travel & ETA"
                  checked={editingGrant.notify.travel}
                  onChange={(v) => updateNotifyFlag("travel", v)}
                />
                <Switch
                  label="Battery dying alerts"
                  checked={editingGrant.notify.battery}
                  onChange={(v) => updateNotifyFlag("battery", v)}
                />
                <Switch
                  label="Schedule changes"
                  checked={editingGrant.notify.schedule_change}
                  onChange={(v) => updateNotifyFlag("schedule_change", v)}
                />
              </div>
            </div>

            {/* Reach-Through Toggle */}
            <div className="pt-2 border-t border-[var(--hairline)]">
              <Switch
                label="Important (Reach-through notifications)"
                checked={editingGrant.reach_through}
                onChange={(v) => setEditingGrant({ ...editingGrant, reach_through: v })}
              />
            </div>

            {saveSuccess ? (
              <p className="text-center font-semibold text-[var(--primary)] text-[14px]">
                ✓ Permissions saved!
              </p>
            ) : (
              <PillButton variant="primary" onClick={handleSaveGrant} disabled={savingGrant} className="w-full">
                {savingGrant ? "Saving..." : "Save Permissions"}
              </PillButton>
            )}
          </div>
        )}
      </BottomSheet>

      <BottomNav current="alerts" />
    </div>
  );
}
