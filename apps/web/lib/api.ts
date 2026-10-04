export type AccessLevel = "none" | "status" | "details";
export type Calls = "ok" | "prefer_not" | "no";
export type Messages = "ok" | "later";

export interface ViewerState {
  owner: string;
  as_of: string;
  activity?: {
    type?: string;
    label?: string;
    until?: string | null;
    layer?: number;
    provenance?: {
      source?: string;
      model?: string;
      confidence?: number;
      confirmed_at?: string;
    };
  } | null;
  reachability?: {
    calls?: Calls | null;
    messages?: Messages | null;
    reason?: string | null;
    until?: string | null;
    free_in_min?: number | null;
  } | null;
  phone?: {
    mode?: string;
    battery_bucket?: string;
    may_go_offline?: boolean;
    declared_offline?: boolean;
    stale?: boolean;
    battery_pct?: number | null;
  } | null;
  current_place?: string | null;
  card_access?: Partial<CardGrants>;
  messages?: Array<{
    id: string;
    text?: string;
    expires_at: string;
    promise_at?: string;
  }>;
  travel?: {
    destination?: string;
    eta?: string | null;
    phase?: string;
    overdue?: boolean;
    companions?: string[];
    vehicle?: string | null;
    mode?: string;
  } | null;
  exam?: {
    state?: string;
    subject?: string | null;
    until?: string | null;
    next_free_window?: string | null;
    exams_today?: number;
  } | null;
  last_shared_context?: {
    snapshot: Record<string, any>;
    shared_at: string;
  } | null;
  next_boundary_at?: string | null;
  sharing_paused?: boolean;
}

export interface UserProfile {
  id: string;
  _id?: string;
  name: string;
  user_code: string;
  email?: string;
  avatar_url?: string | null;
  current_place?: string | null;
  tz?: string;
  routine_prefs?: {
    wake: string;
    sleep: string;
    min_call_window_min: number;
    buffer_min: number;
  };
  sharing_paused?: {
    active: boolean;
    until?: string | null;
  };
  read_only?: boolean;
}

export interface Connection {
  _id?: string;
  id: string;
  a: string;
  b: string;
  status: "pending" | "active" | "blocked";
  requested_by: string;
  other_user?: {
    id: string;
    name: string;
    user_code?: string;
    avatar_url?: string | null;
  };
  target_user?: Connection["other_user"];
  created_at?: string;
}

export interface CardGrants {
  schedule: AccessLevel;
  exam: AccessLevel;
  live: AccessLevel;
  travel: AccessLevel;
  phone: AccessLevel;
  safety: AccessLevel;
  message: AccessLevel;
}

export interface NotifyFlags {
  free_now: boolean;
  activity: boolean;
  phone: boolean;
  exam: boolean;
  travel: boolean;
  battery: boolean;
  schedule_change: boolean;
  message: boolean;
  safety: boolean;
}

export interface Grant {
  _id?: string;
  owner: string;
  viewer: string;
  relationship_preset?: string;
  cards: CardGrants;
  notify: NotifyFlags;
  important: boolean;
  reach_through: boolean;
  expires_at?: string | null;
  revoked_at?: string | null;
}

export interface NotificationItem {
  _id: string;
  to: string;
  about_owner: string;
  kind: string;
  payload_redacted?: {
    text: string;
  };
  action?: string;
  dedupe_key?: string;
  status: string;
  created_at: string;
  read_at?: string | null;
}

export interface ParseResult {
  draft_id?: string;
  intent: string;
  language: string;
  items: any[];
  missing: { field: string; question: string }[];
  confidence: number;
  notes: string[];
}

async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const baseUrl = (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
  let url = input;
  if (input.startsWith("/api/") && baseUrl) {
    url = `${baseUrl}${input.replace(/^\/api/, "")}`;
  }

  const token = typeof window !== "undefined" ? localStorage.getItem("circlecue_token") : null;
  const method = (init?.method || "GET").toUpperCase();
  const authPath = input.replace(/^\/api/, "");
  const publicAuthPath = ["/auth/demo", "/auth/login", "/auth/register", "/auth/logout"].includes(authPath);
  if (token && isReadOnlyDemoToken(token) && !["GET", "HEAD", "OPTIONS"].includes(method) && !publicAuthPath) {
    window.dispatchEvent(new Event("circlecue:demo-write-blocked"));
    throw new Error("This demo is view-only. Sign in or create an account to make changes.");
  }
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...init,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    let errorDetail = "";
    try {
      const rawText = await response.text();
      try {
        const errObj = JSON.parse(rawText);
        const apiError = errObj.error;
        errorDetail = typeof errObj === "string"
          ? errObj
          : errObj.message || errObj.detail || apiError?.message || JSON.stringify(errObj);
      } catch {
        errorDetail = rawText;
      }
    } catch {
      errorDetail = `Request failed with status ${response.status}`;
    }
    throw new Error(errorDetail || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

function isReadOnlyDemoToken(token: string): boolean {
  try {
    const payload = token.split(".")[1];
    if (!payload) return false;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    return JSON.parse(window.atob(padded)).read_only_demo === true;
  } catch {
    return false;
  }
}

export function isReadOnlyDemoSession(): boolean {
  if (typeof window === "undefined") return false;
  const token = localStorage.getItem("circlecue_token");
  return token ? isReadOnlyDemoToken(token) : false;
}

function notifyAuthChanged() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event("circlecue:auth-changed"));
}

// ----------------- Auth -----------------
export async function login(email: string, password: string): Promise<UserProfile> {
  const res = await fetchJson<UserProfile & { token?: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (typeof window !== "undefined" && res.token) {
    localStorage.setItem("circlecue_token", res.token);
    notifyAuthChanged();
  }
  return res;
}

export async function loginDemo(): Promise<UserProfile> {
  const res = await fetchJson<UserProfile & { token?: string }>("/api/auth/demo", { method: "POST" });
  if (typeof window !== "undefined" && res.token) {
    localStorage.setItem("circlecue_token", res.token);
    notifyAuthChanged();
  }
  return { ...res, read_only: true };
}

export async function register(
  name: string,
  email: string,
  password: string,
  tz: string = "UTC",
): Promise<UserProfile> {
  const res = await fetchJson<UserProfile & { token?: string }>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ name, email, password, tz }),
  });
  if (typeof window !== "undefined" && res.token) {
    localStorage.setItem("circlecue_token", res.token);
    notifyAuthChanged();
  }
  return res;
}

export async function logout(): Promise<void> {
  if (typeof window !== "undefined") {
    localStorage.removeItem("circlecue_token");
    notifyAuthChanged();
  }
  await fetchJson("/api/auth/logout", { method: "POST" });
}

// ----------------- Profile & Me -----------------
export async function getMe(): Promise<UserProfile> {
  return fetchJson<UserProfile>("/api/me");
}

export async function updateCurrentPlace(current_place: string): Promise<UserProfile> {
  return await fetchJson<UserProfile>("/api/me", {
    method: "PATCH",
    body: JSON.stringify({ current_place }),
  });
}

export async function updateRoutinePrefs(routine_prefs: UserProfile["routine_prefs"]): Promise<UserProfile> {
  return fetchJson<UserProfile>("/api/me/routine", {
    method: "PATCH",
    body: JSON.stringify(routine_prefs),
  });
}

export async function pauseSharing(active: boolean, until?: string | null): Promise<{ sharing_paused: { active: boolean; until?: string | null } }> {
  return active
    ? fetchJson("/api/me/pause", {
        method: "POST",
        body: JSON.stringify({ until: until ?? null }),
      })
    : fetchJson("/api/me/pause", { method: "DELETE" });
}

export async function exportData(): Promise<Record<string, any>> {
  return fetchJson<Record<string, any>>("/api/me/export");
}

export async function deleteAccount(): Promise<{ message: string }> {
  return fetchJson<{ message: string }>("/api/me", { method: "DELETE" });
}

// ----------------- State & Visibility -----------------
export async function getMyState(): Promise<ViewerState | null> {
  try {
    return await fetchJson<ViewerState>("/api/state/me");
  } catch (error) {
    console.warn("state/me error", error);
    return null;
  }
}

export async function getViewerState(userId: string): Promise<ViewerState | null> {
  return fetchJson<ViewerState>(`/api/state/${userId}`);
}

export interface ViewerTimeline {
  date: string;
  tz: string;
  sharing_paused?: boolean;
  segments: Array<{
    start: string;
    end: string;
    activity_type: string;
    label: string;
    calls?: string;
    calls_ok?: boolean;
  }>;
}

export async function getViewerTimeline(userId: string): Promise<ViewerTimeline | null> {
  try {
    return await fetchJson<ViewerTimeline>(`/api/timeline/${userId}`);
  } catch {
    return null;
  }
}

// ----------------- Connections -----------------
export async function getConnections(): Promise<Connection[]> {
  const records = await fetchJson<Connection[]>("/api/connections");
  return records.map((connection) => ({
    ...connection,
    _id: connection.id || connection._id,
    other_user: connection.other_user || connection.target_user,
  }));
}

export async function lookupUser(code: string): Promise<UserProfile> {
  return fetchJson<UserProfile>(`/api/users/code-lookup?code=${encodeURIComponent(code)}`);
}

export async function sendConnectionRequest(userCode: string): Promise<Connection> {
  return fetchJson<Connection>("/api/connections/request", {
    method: "POST",
    body: JSON.stringify({ user_code: userCode }),
  });
}

export async function respondToConnection(connectionId: string, accept: boolean): Promise<void> {
  const action = accept ? "accept" : "decline";
  await fetchJson(`/api/connections/${connectionId}/${action}`, { method: "POST" });
}

export async function removeConnection(connectionId: string): Promise<void> {
  await fetchJson(`/api/connections/${connectionId}`, { method: "DELETE" });
}

// ----------------- Grants -----------------
export async function getGrants(): Promise<Grant[]> {
  return fetchJson<Grant[]>("/api/grants/outgoing");
}

export async function getGrant(connectionId: string): Promise<Grant | null> {
  try {
    return await fetchJson<Grant>(`/api/grants/${connectionId}`);
  } catch {
    return null;
  }
}

export async function updateGrant(connectionId: string, grant: Partial<Grant>): Promise<Grant> {
  return fetchJson<Grant>(`/api/grants/${connectionId}`, {
    method: "PUT",
    body: JSON.stringify(grant),
  });
}

// ----------------- Cards -----------------
export async function getCards(cardType: string): Promise<any> {
  return fetchJson(`/api/cards/${cardType}`);
}

export async function createCard(cardType: string, payload: any): Promise<any> {
  return fetchJson(`/api/cards/${cardType}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function saveSchedule(templates: any[]): Promise<any> {
  return fetchJson("/api/cards/schedule/bulk", {
    method: "PUT",
    body: JSON.stringify({ templates }),
  });
}

export async function updateCard(cardType: string, cardId: string, payload: any): Promise<any> {
  return fetchJson(`/api/cards/${cardType}/${cardId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteCard(cardType: string, cardId: string, version: number = 1): Promise<any> {
  return fetchJson(`/api/cards/${cardType}/${cardId}?version=${version}`, {
    method: "DELETE",
  });
}

// ----------------- AI Parsing & Confirmation -----------------
export async function parseText(text: string, mode: string = "activity"): Promise<ParseResult> {
  return fetchJson<ParseResult>("/api/ai/parse", {
    method: "POST",
    body: JSON.stringify({
      text,
      mode,
      client_now: new Date().toISOString(),
      tz: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    }),
  });
}

export async function confirmDraft(items: any[], draftId?: string): Promise<any> {
  return fetchJson("/api/ai/confirm", {
    method: "POST",
    body: JSON.stringify({
      draft_id: draftId,
      items,
    }),
  });
}

// ----------------- Notifications -----------------
export async function getNotifications(): Promise<NotificationItem[]> {
  return fetchJson<NotificationItem[]>("/api/notifications");
}

export async function markNotificationRead(id: string): Promise<void> {
  await fetchJson(`/api/notifications/${id}/read`, { method: "POST" });
}

export function subscribeToNotifications(
  onMessage: (notification: NotificationItem) => void,
  onError?: () => void,
) {
  const source = new EventSource("/api/notifications/stream");
  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as NotificationItem;
      onMessage(payload);
    } catch (error) {
      console.warn("notification stream parse failed", error);
    }
  };
  source.onerror = () => {
    onError?.();
  };
  return source;
}
