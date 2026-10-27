export type QueueItem = {
  id: number;
  status: string;
  kind: string;
  inbound_text: string;
  draft_subject: string | null;
  draft_body: string | null;
  cited_pages: string[];
  page_excerpts: Record<string, string>;
  slot_held: boolean;
  created_at: string;
};

export type OutboxItem = {
  id: number;
  kind: string;
  subject: string | null;
  body: string;
  to_email: string | null;
  delivered: boolean;
  delivery_error: string | null;
  sent_at: string;
  source_task_id: number | null;
};

export type InboxMessage = {
  id: number;
  sampleId: string | null;
  from: string;
  fromEmail: string;
  subject: string;
  receivedLabel: string;
  body: string;
  channel: string;
};

export type MessageResult = {
  task_id: number;
  outcome_kind: string;
  message: string;
  auto_reply_text: string | null;
  queue_status: string | null;
};

export type HealthStatus = {
  status: string;
  openai_configured: boolean;
  smtp_configured: boolean;
  inbound_automation_ready: boolean;
  inbound_resend_api_full_access: boolean;
  inbound_webhook_configured: boolean;
  inbound_setup_note: string;
  inbound_address: string;
  pages_dir: string;
  pending_count: number;
};

export type CreateStaffPayload = {
  username: string;
  password: string;
  role: "staff" | "manager";
  display_name?: string | null;
  email?: string | null;
};

export type StaffUser = {
  username: string;
  role: "staff" | "manager";
  display_name: string | null;
  email?: string | null;
};

export type StaffAdminUser = {
  username: string;
  role: "staff" | "manager";
  email: string | null;
  mfa_enabled: boolean;
  active: boolean;
};

export type Me = {
  user: StaffUser;
  mfa_enabled: boolean;
};

export type MfaSetup = {
  secret: string;
  otpauth_uri: string;
  qr_data_uri: string;
};

export type LoginResult = {
  user: StaffUser;
  mfaRequired: boolean;
  mfaToken: string | null;
};

const TOKEN_KEY = "clerk_access_token";
const REFRESH_KEY = "clerk_refresh_token";
const REFRESH_LEAD_SECONDS = 120;

let refreshInFlight: Promise<boolean> | null = null;
let proactiveRefreshTimer: ReturnType<typeof setTimeout> | null = null;
let onSessionLost: (() => void) | null = null;

function clearProactiveRefreshTimer(): void {
  if (proactiveRefreshTimer !== null) {
    clearTimeout(proactiveRefreshTimer);
    proactiveRefreshTimer = null;
  }
}

function accessTokenExpiresAtMs(accessToken: string): number | null {
  const parts = accessToken.split(".");
  if (parts.length !== 3) {
    return null;
  }
  try {
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(base64)) as { exp?: unknown };
    if (typeof payload.exp === "number") {
      return payload.exp * 1000;
    }
  } catch {
    return null;
  }
  return null;
}

function accessTokenNeedsRefresh(accessToken: string): boolean {
  const expMs = accessTokenExpiresAtMs(accessToken);
  if (expMs === null) {
    return true;
  }
  return expMs - Date.now() <= REFRESH_LEAD_SECONDS * 1000;
}

function scheduleProactiveRefresh(): void {
  clearProactiveRefreshTimer();
  const accessToken = sessionStorage.getItem(TOKEN_KEY);
  if (!accessToken || !sessionStorage.getItem(REFRESH_KEY)) {
    return;
  }
  const expMs = accessTokenExpiresAtMs(accessToken);
  if (expMs === null) {
    return;
  }
  const delayMs = Math.max(expMs - Date.now() - REFRESH_LEAD_SECONDS * 1000, 5_000);
  proactiveRefreshTimer = setTimeout(() => {
    void rotateRefreshCredential(true);
  }, delayMs);
}

function failLocalSession(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
  clearProactiveRefreshTimer();
  onSessionLost?.();
}

async function rotateRefreshCredential(scheduleNext: boolean): Promise<boolean> {
  if (refreshInFlight) {
    return refreshInFlight;
  }
  const rawRefresh = sessionStorage.getItem(REFRESH_KEY);
  if (!rawRefresh) {
    return false;
  }
  refreshInFlight = (async () => {
    try {
      const response = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rawRefresh }),
      });
      if (!response.ok) {
        return false;
      }
      const parsed = (await response.json()) as {
        access_token?: string | null;
        refresh_token?: string | null;
      };
      if (!parsed.access_token) {
        return false;
      }
      storeSessionTokens(parsed.access_token, parsed.refresh_token ?? rawRefresh);
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  const ok = await refreshInFlight;
  if (!ok) {
    failLocalSession();
    return false;
  }
  if (scheduleNext) {
    scheduleProactiveRefresh();
  }
  return true;
}

async function ensureFreshAccessToken(): Promise<boolean> {
  const accessToken = sessionStorage.getItem(TOKEN_KEY);
  if (!accessToken) {
    return false;
  }
  if (!accessTokenNeedsRefresh(accessToken)) {
    return true;
  }
  return rotateRefreshCredential(true);
}

function authHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  headers.set("Content-Type", "application/json");
  return headers;
}

async function authorizedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (sessionStorage.getItem(TOKEN_KEY)) {
    const fresh = await ensureFreshAccessToken();
    if (!fresh) {
      return new Response(JSON.stringify({ detail: "Not authenticated." }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }
  }
  let response = await fetch(input, {
    ...init,
    headers: authHeaders(init?.headers),
  });
  if (response.status === 401 && sessionStorage.getItem(REFRESH_KEY)) {
    const refreshed = await rotateRefreshCredential(true);
    if (refreshed) {
      response = await fetch(input, {
        ...init,
        headers: authHeaders(init?.headers),
      });
    }
  }
  return response;
}

function storeSessionTokens(accessToken: string, refreshToken: string | null | undefined): void {
  sessionStorage.setItem(TOKEN_KEY, accessToken);
  if (refreshToken) {
    sessionStorage.setItem(REFRESH_KEY, refreshToken);
  } else {
    sessionStorage.removeItem(REFRESH_KEY);
  }
  scheduleProactiveRefresh();
}

export function hasSession(): boolean {
  return Boolean(sessionStorage.getItem(TOKEN_KEY));
}

export function startSessionMaintenance(onLost: () => void): () => void {
  onSessionLost = onLost;
  scheduleProactiveRefresh();
  void ensureFreshAccessToken();
  return () => {
    onSessionLost = null;
    clearProactiveRefreshTimer();
  };
}

function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (detail && typeof detail === "object" && "detail" in detail) {
    return formatApiDetail((detail as { detail: unknown }).detail);
  }
  return "Request failed";
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authorizedFetch(path, init);
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      message = formatApiDetail(body.detail ?? body);
    } catch {
      message = await response.text();
    }
    throw new Error(message || response.statusText);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

type TokenResponse = {
  access_token: string | null;
  refresh_token: string | null;
  username: string;
  role: "staff" | "manager";
  mfa_required: boolean;
  mfa_token: string | null;
};

function userFromToken(parsed: TokenResponse): StaffUser {
  return { username: parsed.username, role: parsed.role, display_name: null, email: null };
}

async function publicJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      message = formatApiDetail(body.detail ?? body);
    } catch {
      message = await response.text();
    }
    throw new Error(message || response.statusText);
  }
  return (await response.json()) as T;
}

export async function fetchDemoStatus(): Promise<boolean> {
  const parsed = await api<{ available: boolean }>("/api/auth/demo-status");
  return Boolean(parsed.available);
}

export async function loginDemo(): Promise<StaffUser> {
  const parsed = await api<TokenResponse>("/api/auth/demo", { method: "POST" });
  if (!parsed.access_token || !parsed.refresh_token) {
    throw new Error("Demo login did not return session tokens.");
  }
  storeSessionTokens(parsed.access_token, parsed.refresh_token);
  return userFromToken(parsed);
}

export async function login(username: string, password: string): Promise<LoginResult> {
  const parsed = await api<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  if (parsed.mfa_required) {
    return {
      user: userFromToken(parsed),
      mfaRequired: true,
      mfaToken: parsed.mfa_token,
    };
  }
  if (!parsed.access_token || !parsed.refresh_token) {
    throw new Error("Login did not return session tokens.");
  }
  storeSessionTokens(parsed.access_token, parsed.refresh_token);
  return {
    user: userFromToken(parsed),
    mfaRequired: false,
    mfaToken: null,
  };
}

export async function completeMfaLogin(mfaToken: string, code: string): Promise<StaffUser> {
  const parsed = await api<TokenResponse>("/api/auth/login/mfa", {
    method: "POST",
    body: JSON.stringify({ mfa_token: mfaToken, code }),
  });
  if (!parsed.access_token || !parsed.refresh_token) {
    throw new Error("Sign-in did not return session tokens.");
  }
  storeSessionTokens(parsed.access_token, parsed.refresh_token);
  return userFromToken(parsed);
}

export async function fetchMe(): Promise<Me> {
  return api<Me>("/api/auth/me");
}

export async function fetchSession(): Promise<StaffUser | null> {
  if (!hasSession()) {
    return null;
  }
  try {
    const me = await fetchMe();
    return me.user;
  } catch {
    failLocalSession();
    return null;
  }
}

export async function forgotPassword(username: string): Promise<{
  message: string;
  dev_reset_token?: string | null;
}> {
  return publicJson("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ username }),
  });
}

export async function resetPassword(token: string, password: string): Promise<string> {
  const parsed = await publicJson<{ message: string }>("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
  return parsed.message;
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<string> {
  const parsed = await api<{ message: string }>("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  return parsed.message;
}

export async function updateEmail(email: string): Promise<StaffUser> {
  return api<StaffUser>("/api/auth/profile/email", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function startMfaSetup(password: string): Promise<MfaSetup> {
  return api<MfaSetup>("/api/auth/mfa/setup", {
    method: "POST",
    body: JSON.stringify({ password }),
  });
}

export async function confirmMfaSetup(code: string): Promise<string[]> {
  const parsed = await api<{ recovery_codes: string[] }>("/api/auth/mfa/confirm", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
  return parsed.recovery_codes;
}

export async function disableMfa(password: string, code: string): Promise<string> {
  const parsed = await api<{ message: string }>("/api/auth/mfa/disable", {
    method: "POST",
    body: JSON.stringify({ password, code }),
  });
  return parsed.message;
}

export async function regenerateRecoveryCodes(password: string, code: string): Promise<string[]> {
  const parsed = await api<{ recovery_codes: string[] }>("/api/auth/mfa/recovery-codes/regenerate", {
    method: "POST",
    body: JSON.stringify({ password, code }),
  });
  return parsed.recovery_codes;
}

export async function fetchStaffUsers(): Promise<StaffAdminUser[]> {
  return api<StaffAdminUser[]>("/api/staff/users");
}

export async function clearStaffMfa(username: string): Promise<void> {
  await api(`/api/staff/users/${encodeURIComponent(username)}/mfa/reset`, { method: "POST" });
}

export async function setStaffUserRole(
  username: string,
  role: "staff" | "manager",
): Promise<StaffAdminUser> {
  return api<StaffAdminUser>(`/api/staff/users/${encodeURIComponent(username)}/role`, {
    method: "POST",
    body: JSON.stringify({ role }),
  });
}

export async function setStaffUserDisabled(
  username: string,
  disabled: boolean,
): Promise<StaffAdminUser> {
  const action = disabled ? "disable" : "enable";
  return api<StaffAdminUser>(`/api/staff/users/${encodeURIComponent(username)}/${action}`, {
    method: "POST",
  });
}

export async function createStaffUser(payload: CreateStaffPayload): Promise<StaffUser> {
  return api<StaffUser>("/api/staff/users", {
    method: "POST",
    body: JSON.stringify({
      username: payload.username,
      password: payload.password,
      role: payload.role,
      display_name: payload.display_name ?? null,
      email: payload.email ?? null,
    }),
  });
}

function formatInboxTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function mapInbound(row: {
  id: number;
  from_name: string;
  from_email: string;
  subject: string;
  body: string;
  channel: string;
  sample_id: string | null;
  created_at: string;
}): InboxMessage {
  return {
    id: row.id,
    sampleId: row.sample_id,
    from: row.from_name,
    fromEmail: row.from_email,
    subject: row.subject,
    body: row.body,
    channel: row.channel,
    receivedLabel: formatInboxTime(row.created_at),
  };
}

export async function fetchInbox(): Promise<InboxMessage[]> {
  const rows = await api<
    {
      id: number;
      from_name: string;
      from_email: string;
      subject: string;
      body: string;
      channel: string;
      sample_id: string | null;
      created_at: string;
    }[]
  >("/api/inbox");
  return rows.map(mapInbound);
}

export async function resetDemoInbox(): Promise<string> {
  const parsed = await api<{ message: string }>("/api/inbox/reset-demo", { method: "POST" });
  return parsed.message;
}

export async function createInboundMessage(payload: {
  from_name: string;
  from_email: string;
  subject: string;
  body: string;
  channel?: string;
}): Promise<InboxMessage> {
  const row = await api<{
    id: number;
    from_name: string;
    from_email: string;
    subject: string;
    body: string;
    channel: string;
    sample_id: string | null;
    created_at: string;
  }>("/api/inbox", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return mapInbound(row);
}

export async function logout(): Promise<void> {
  const refresh = sessionStorage.getItem(REFRESH_KEY);
  if (refresh) {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
    } catch {
      // still clear local session
    }
  }
  failLocalSession();
}

export async function fetchHealth(): Promise<HealthStatus> {
  return api("/api/health");
}

export async function submitMessage(
  text: string,
  options?: {
    sampleId?: string | null;
    inboundId?: number;
    replyToEmail?: string;
    inboundSubject?: string;
  },
): Promise<MessageResult> {
  return api("/api/messages", {
    method: "POST",
    body: JSON.stringify({
      text,
      sample_id: options?.sampleId ?? null,
      inbound_id: options?.inboundId ?? null,
      reply_to_email: options?.replyToEmail ?? null,
      inbound_subject: options?.inboundSubject ?? null,
    }),
  });
}

export async function fetchQueue(): Promise<QueueItem[]> {
  return api("/api/queue");
}

export async function approveTask(taskId: number): Promise<void> {
  await api(`/api/queue/${taskId}/approve`, { method: "POST" });
}

export async function rejectTask(taskId: number): Promise<void> {
  await api(`/api/queue/${taskId}/reject`, { method: "POST" });
}

export async function fetchOutbox(): Promise<OutboxItem[]> {
  return api("/api/outbox");
}
