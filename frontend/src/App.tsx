import { useCallback, useEffect, useState } from "react";

import {
  approveTask,
  fetchHealth,
  fetchInbox,
  fetchMe,
  fetchOutbox,
  fetchQueue,
  fetchSession,
  logout,
  type StaffUser,
  rejectTask,
  startSessionMaintenance,
  submitMessage,
  type HealthStatus,
  type InboxMessage,
  type MessageResult,
  type OutboxItem,
  type QueueItem,
} from "./api";
import { AuthScreen } from "./components/AuthScreen";
import { ClerkWorkspace } from "./components/ClerkWorkspace";
import { PeoplePanel } from "./components/PeoplePanel";
import { SecurityPanel } from "./components/SecurityPanel";

export function App() {
  const [user, setUser] = useState<StaffUser | null>(null);
  const [demoDesk, setDemoDesk] = useState(false);
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [securityOpen, setSecurityOpen] = useState(false);
  const [peopleOpen, setPeopleOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [outbox, setOutbox] = useState<OutboxItem[]>([]);
  const [inbox, setInbox] = useState<InboxMessage[]>([]);
  const [selected, setSelected] = useState<InboxMessage | null>(null);
  const [processedIds, setProcessedIds] = useState<Set<string>>(() => new Set());
  const [lastResult, setLastResult] = useState<MessageResult | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [q, o, h, i] = await Promise.all([
      fetchQueue(),
      fetchOutbox(),
      fetchHealth(),
      fetchInbox(),
    ]);
    setQueue(q);
    setOutbox(o);
    setHealth(h);
    setInbox(i);
  }, []);

  async function loadMe() {
    const me = await fetchMe();
    setUser(me.user);
    setDemoDesk(Boolean(me.demo_desk));
    setMfaEnabled(me.mfa_enabled);
  }

  async function handleSignedIn(signedIn: StaffUser) {
    setUser(signedIn);
    try {
      await loadMe();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load session.");
    }
  }

  async function handleLogout() {
    await logout();
    setUser(null);
    setDemoDesk(false);
    setMfaEnabled(false);
    sessionStorage.removeItem("clerk_demo_sent_after");
    setSecurityOpen(false);
    setPeopleOpen(false);
    setQueue([]);
    setOutbox([]);
    setInbox([]);
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
      const result = await submitMessage(message.body, {
        sampleId: message.sampleId,
        inboundId: message.id,
        replyToEmail: message.fromEmail,
        inboundSubject: message.subject,
      });
      setLastResult(result);
      setProcessedIds((prev) => new Set(prev).add(String(message.id)));
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
      setLastResult((current) =>
        current && current.task_id === taskId
          ? {
              ...current,
              outcome_kind: "approved",
              message: "Sent.",
              queue_status: "approved",
              auto_reply_text: null,
            }
          : current,
      );
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
      setLastResult((current) =>
        current && current.task_id === taskId
          ? {
              ...current,
              outcome_kind: "rejected",
              message: "Rejected. Nothing was sent.",
              queue_status: "rejected",
              auto_reply_text: null,
            }
          : current,
      );
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
        void loadMe()
          .then(() => refresh())
          .catch(() => setUser(null));
      }
    });
  }, [refresh]);

  useEffect(() => {
    if (!user) {
      return;
    }
    return startSessionMaintenance(() => {
      setUser(null);
      setQueue([]);
      setOutbox([]);
    });
  }, [user]);

  useEffect(() => {
    if (!user || securityOpen) {
      return;
    }
    const timer = window.setInterval(() => {
      void refresh();
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [user, securityOpen, refresh]);

  if (!user) {
    return <AuthScreen onSignedIn={(signedIn) => void handleSignedIn(signedIn)} />;
  }

  if (securityOpen) {
    return (
      <SecurityPanel
        user={user}
        mfaEnabled={mfaEnabled}
        onBack={() => setSecurityOpen(false)}
        onMfaEnabledChange={setMfaEnabled}
        onUserUpdate={setUser}
      />
    );
  }

  if (peopleOpen && user.role === "manager") {
    return (
      <PeoplePanel
        signedInUsername={user.username}
        onBack={() => setPeopleOpen(false)}
      />
    );
  }

  return (
    <ClerkWorkspace
      user={user}
      demoDesk={demoDesk}
      mfaEnabled={mfaEnabled}
      health={health}
      inbox={inbox}
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
      onOpenSecurity={() => {
        setPeopleOpen(false);
        setSecurityOpen(true);
      }}
      onOpenPeople={
        user.role === "manager"
          ? () => {
              setSecurityOpen(false);
              setPeopleOpen(true);
            }
          : undefined
      }
      onLogout={() => void handleLogout()}
      onInboxChanged={() => void refresh()}
    />
  );
}
