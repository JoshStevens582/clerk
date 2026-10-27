import { useCallback, useEffect, useState } from "react";

import {
  approveTask,
  fetchHealth,
  fetchOutbox,
  fetchQueue,
  fetchSession,
  login,
  logout,
  type StaffUser,
  rejectTask,
  submitMessage,
  type HealthStatus,
  type MessageResult,
  type OutboxItem,
  type QueueItem,
} from "./api";
import { ClerkWorkspace } from "./components/ClerkWorkspace";
import { LoginScreen } from "./components/LoginScreen";
import type { InboxMessage } from "./inbox";

export function App() {
  const [user, setUser] = useState<StaffUser | null>(null);
  const [username, setUsername] = useState("reception");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [outbox, setOutbox] = useState<OutboxItem[]>([]);
  const [selected, setSelected] = useState<InboxMessage | null>(null);
  const [processedIds, setProcessedIds] = useState<Set<string>>(() => new Set());
  const [lastResult, setLastResult] = useState<MessageResult | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [q, o, h] = await Promise.all([fetchQueue(), fetchOutbox(), fetchHealth()]);
    setQueue(q);
    setOutbox(o);
    setHealth(h);
  }, []);

  async function handleLogin(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const signedIn = await login(username, password);
      setUser(signedIn);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  async function handleLogout() {
    await logout();
    setUser(null);
    setQueue([]);
    setOutbox([]);
    setLastResult(null);
    setSelected(null);
    setProcessedIds(new Set());
    setHealth(null);
  }

  async function handleSelectInbox(message: InboxMessage) {
    setSelected(message);
    setBusy(true);
    setError(null);
    try {
      const result = await submitMessage(message.body, message.sampleId);
      setLastResult(result);
      setProcessedIds((prev) => new Set(prev).add(message.id));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove(taskId: number) {
    setBusy(true);
    setError(null);
    try {
      await approveTask(taskId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleReject(taskId: number) {
    setBusy(true);
    setError(null);
    try {
      await rejectTask(taskId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reject failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void fetchSession().then((session) => {
      if (session?.username) {
        setUser(session);
        void refresh();
      }
    });
  }, [refresh]);

  useEffect(() => {
    if (!user) {
      return;
    }
    const timer = window.setInterval(() => {
      void refresh();
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [user, refresh]);

  if (!user) {
    return (
      <LoginScreen
        username={username}
        password={password}
        error={error}
        onUsernameChange={setUsername}
        onPasswordChange={setPassword}
        onSubmit={handleLogin}
      />
    );
  }

  return (
    <ClerkWorkspace
      user={user}
      health={health}
      queue={queue}
      outbox={outbox}
      selected={selected}
      processedIds={processedIds}
      lastResult={lastResult}
      busy={busy}
      error={error}
      onSelectInbox={(message) => void handleSelectInbox(message)}
      onApprove={handleApprove}
      onReject={handleReject}
      onLogout={() => void handleLogout()}
    />
  );
}
