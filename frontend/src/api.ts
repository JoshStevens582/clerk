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
  sent_at: string;
  source_task_id: number | null;
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
  pages_dir: string;
  pending_count: number;
};

export type StaffUser = {
  username: string;
  role: "staff" | "manager";
  display_name: string | null;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return (await response.json()) as T;
}

export async function login(username: string, password: string): Promise<StaffUser> {
  const result = await api<{ user: StaffUser }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  return result.user;
}

export async function fetchSession(): Promise<StaffUser | null> {
  return api<StaffUser | null>("/api/auth/session");
}

export async function logout(): Promise<void> {
  await api("/api/auth/logout", { method: "POST" });
}

export async function fetchHealth(): Promise<HealthStatus> {
  return api("/api/health");
}

export async function submitMessage(
  text: string,
  sampleId?: string,
): Promise<MessageResult> {
  return api("/api/messages", {
    method: "POST",
    body: JSON.stringify({ text, sample_id: sampleId ?? null }),
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
