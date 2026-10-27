import { useEffect, useState } from "react";

import {
  createInboundMessage,
  resetDemoInbox,
  type HealthStatus,
  type InboxMessage,
  type MessageResult,
  type OutboxItem,
  type QueueItem,
  type StaffUser,
} from "../api";
import { kindLabel } from "../labels";

type MobilePane = "inbox" | "desk" | "sent";

type ClerkWorkspaceProps = {
  user: StaffUser;
  mfaEnabled: boolean;
  health: HealthStatus | null;
  inbox: InboxMessage[];
  queue: QueueItem[];
  outbox: OutboxItem[];
  selected: InboxMessage | null;
  processedIds: Set<string>;
  lastResult: MessageResult | null;
  busy: boolean;
  error: string | null;
  onSelectInbox: (message: InboxMessage) => void;
  onApprove: (taskId: number) => void;
  onReject: (taskId: number) => void;
  onOpenSecurity: () => void;
  onOpenPeople?: () => void;
  onLogout: () => void;
  onInboxChanged: () => void;
};

export function ClerkWorkspace({
  user,
  mfaEnabled,
  health,
  inbox,
  queue,
  outbox,
  selected,
  processedIds,
  lastResult,
  busy,
  error,
  onSelectInbox,
  onApprove,
  onReject,
  onOpenSecurity,
  onOpenPeople,
  onLogout,
  onInboxChanged,
}: ClerkWorkspaceProps) {
  const pending = queue.length;
  const [showAddInbound, setShowAddInbound] = useState(false);
  const [inboundForm, setInboundForm] = useState({
    from_name: "",
    from_email: "",
    subject: "",
    body: "",
    channel: "Email",
  });
  const [inboundError, setInboundError] = useState<string | null>(null);
  const [mobilePane, setMobilePane] = useState<MobilePane>("desk");
  const [sentCollapsed, setSentCollapsed] = useState(false);

  useEffect(() => {
    if (selected) {
      setMobilePane("desk");
    }
  }, [selected]);

  async function onSubmitInbound(event: React.FormEvent) {
    event.preventDefault();
    setInboundError(null);
    try {
      await createInboundMessage(inboundForm);
      setInboundForm({ from_name: "", from_email: "", subject: "", body: "", channel: "Email" });
      setShowAddInbound(false);
      onInboxChanged();
    } catch (err) {
      setInboundError(err instanceof Error ? err.message : "Could not add message.");
    }
  }

  const appClass = [
    "app",
    "app--clerk",
    sentCollapsed ? "app--sent-collapsed" : "",
    `app--mobile-${mobilePane}`,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={appClass}>
      <nav className="mobile-pane-tabs" aria-label="Workspace sections">
        <button
          type="button"
          className={mobilePane === "inbox" ? "active" : ""}
          onClick={() => setMobilePane("inbox")}
        >
          Inbox
          {inbox.length > 0 ? ` (${inbox.length})` : ""}
        </button>
        <button
          type="button"
          className={mobilePane === "desk" ? "active" : ""}
          onClick={() => setMobilePane("desk")}
        >
          Desk
          {pending > 0 ? ` (${pending})` : ""}
        </button>
        <button
          type="button"
          className={mobilePane === "sent" ? "active" : ""}
          onClick={() => setMobilePane("sent")}
        >
          Sent
          {outbox.length > 0 ? ` (${outbox.length})` : ""}
        </button>
      </nav>
      <aside className="panel sidebar">
        <div className="brand">
          <img src="/brand/clerk-mark.svg" alt="" className="brand-mark" width={40} height={40} />
          <div className="brand-text">
            <strong>CLERK</strong>
            <span>Inbox desk — draft from your pages, you approve sends</span>
          </div>
        </div>
        <p className="product-audience">For staff · approval before send</p>
        <p className="workspace-name">Demo clinic: Cape Town Physio</p>
        <p className="product-one-liner">
          Not Counter (visitor chat) or Atlas (handbook) — this runs on patient email and your
          outbox queue.
        </p>
        {health?.inbound_address ? (
          <p className="muted-copy inbox-hint">
            Patient address: <strong>{health.inbound_address}</strong>
            {health.inbound_automation_ready
              ? " — Clerk pulls mail from Resend automatically."
              : health.inbound_setup_note
                ? ` — ${health.inbound_setup_note}`
                : " — inbound not configured yet."}
          </p>
        ) : null}
        <p className="section-label">
          Signed in as {user.username}
          {user.role === "manager" ? " · manager" : ""}
        </p>
        <div className="health">
          <span
            className={`pill ${health === null ? "" : health.openai_configured ? "ok" : "warn"}`}
          >
            {health === null
              ? "Checking…"
              : health.openai_configured
                ? "OpenAI ready"
                : "OpenAI not set"}
          </span>
          <span className={`pill ${health === null ? "" : health.smtp_configured ? "ok" : "warn"}`}>
            {health === null
              ? "Mail…"
              : health.smtp_configured
                ? "SMTP ready"
                : "SMTP not set"}
          </span>
          <span className={`pill ${pending > 0 ? "warn" : "ok"}`}>
            {pending} awaiting approval
          </span>
          <span
            className={`pill ${
              health === null
                ? ""
                : health.inbound_automation_ready
                  ? "ok"
                  : "warn"
            }`}
          >
            {health === null
              ? "Inbound…"
              : health.inbound_automation_ready
                ? "Inbound automation on"
                : "Inbound not live"}
          </span>
        </div>
        {queue.length > 0 ? (
          <>
            <p className="section-label">Needs your approval ({queue.length})</p>
            <div className="stack approval-sidebar">
              {queue.map((item) => (
                <div key={item.id} className="source-card approval-card">
                  <strong>{kindLabel(item.kind)}</strong>
                  <p className="inbound-ref">
                    {item.inbound_text.length > 80
                      ? `${item.inbound_text.slice(0, 80)}…`
                      : item.inbound_text}
                  </p>
                  <div className="approval-actions">
                    <button
                      type="button"
                      className="send"
                      disabled={busy}
                      onClick={() => onApprove(item.id)}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="ghost-btn"
                      disabled={busy}
                      onClick={() => onReject(item.id)}
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : null}
        <p className="section-label">Inbox — not handled yet</p>
        <p className="muted-copy inbox-hint">
          Messages disappear after you open them once. Approvals stay in the list above until you
          approve or reject.
        </p>
        {user.role === "manager" ? (
          <button
            type="button"
            className="ghost"
            disabled={busy}
            onClick={() => {
              void resetDemoInbox()
                .then(() => onInboxChanged())
                .catch((err) => {
                  setInboundError(
                    err instanceof Error ? err.message : "Could not reset demo inbox.",
                  );
                });
            }}
          >
            Reset demo inbox
          </button>
        ) : null}
        <button
          type="button"
          className="new-chat"
          onClick={() => setShowAddInbound((open) => !open)}
        >
          {showAddInbound ? "Cancel" : "Add inbound message"}
        </button>
        {showAddInbound ? (
          <form className="inbound-form" onSubmit={(e) => void onSubmitInbound(e)}>
            {inboundError ? <p className="error">{inboundError}</p> : null}
            <label>
              From name
              <input
                required
                value={inboundForm.from_name}
                onChange={(e) => setInboundForm({ ...inboundForm, from_name: e.target.value })}
              />
            </label>
            <label>
              From email
              <input
                required
                type="email"
                value={inboundForm.from_email}
                onChange={(e) => setInboundForm({ ...inboundForm, from_email: e.target.value })}
              />
            </label>
            <label>
              Subject
              <input
                required
                value={inboundForm.subject}
                onChange={(e) => setInboundForm({ ...inboundForm, subject: e.target.value })}
              />
            </label>
            <label>
              Message
              <textarea
                required
                rows={4}
                value={inboundForm.body}
                onChange={(e) => setInboundForm({ ...inboundForm, body: e.target.value })}
              />
            </label>
            <button type="submit" className="send" disabled={busy}>
              Save to inbox
            </button>
          </form>
        ) : null}
        <div className="stack">
          {inbox.length === 0 ? (
            <p className="muted-copy">No open messages. Add one or use the webhook.</p>
          ) : (
            inbox.map((message) => {
              const isActive = selected?.id === message.id;
              const handled = processedIds.has(String(message.id));
              return (
                <button
                  key={message.id}
                  type="button"
                  className={`row ${isActive ? "active" : ""}`}
                  disabled={busy}
                  onClick={() => onSelectInbox(message)}
                >
                  <span>
                    {message.subject}
                    <small>
                      {message.from} · {message.receivedLabel}
                      {handled ? " · Handled" : ""}
                    </small>
                  </span>
                </button>
              );
            })
          )}
        </div>
        {onOpenPeople ? (
          <button type="button" className="new-chat" onClick={onOpenPeople}>
            People
          </button>
        ) : null}
        <button type="button" className="new-chat" onClick={onOpenSecurity}>
          Security{mfaEnabled ? " · MFA on" : ""}
        </button>
        <button type="button" className="new-chat" onClick={onLogout}>
          Sign out
        </button>
        <p className="suite-links">
          <span className="suite-links-lead">Other products</span>
          <a href="https://counter.customchatandautomation.co.za" target="_blank" rel="noreferrer">
            Counter
          </a>
          <span className="suite-muted"> visitor chat</span>
          {" · "}
          <a href="https://atlas.customchatandautomation.co.za" target="_blank" rel="noreferrer">
            Atlas
          </a>
          <span className="suite-muted"> staff handbook</span>
        </p>
      </aside>

      <main className="panel main">
        <header className="chat-header">
          {selected ? (
            <>
              <h1>{selected.subject}</h1>
              <p>
                {selected.from} · {selected.channel} · {selected.receivedLabel}
              </p>
              <div className="pipeline">
                <div className={`step ${lastResult ? "active" : ""}`}>
                  <b>1. Read pages</b>
                  Policy and approved replies
                </div>
                <div
                  className={`step ${lastResult?.outcome_kind === "queued" ? "active" : lastResult ? "active" : ""}`}
                >
                  <b>2. Act</b>
                  Auto-send or draft
                </div>
                <div className={`step ${pending > 0 ? "active" : ""}`}>
                  <b>3. Approve</b>
                  Owner yes on commitments
                </div>
              </div>
            </>
          ) : (
            <>
              <h1>Inbox desk</h1>
              <p>
                Clerk reads patient mail, pulls facts from approved pages, and queues drafts — nothing
                sends until staff approve.
              </p>
            </>
          )}
        </header>

        <div className="workspace-body">
          {error ? <p className="error banner">{error}</p> : null}

          {queue.length > 0 ? (
            <section className="approval-section approval-section-top">
              <p className="section-label">Awaiting your approval</p>
              {queue.map((item) => (
                <div key={item.id} className="source-card approval-card">
                  <header>
                    <strong>{kindLabel(item.kind)}</strong>
                    <span className="score">{new Date(item.created_at).toLocaleString()}</span>
                  </header>
                  <p className="inbound-ref">{item.inbound_text}</p>
                  {item.draft_subject ? <h3 className="draft-heading">{item.draft_subject}</h3> : null}
                  {item.draft_body ? <pre className="draft-text">{item.draft_body}</pre> : null}
                  {item.cited_pages.map((page) => (
                    <details key={page} className="page-source">
                      <summary>{page}</summary>
                      <pre>{item.page_excerpts[page] ?? ""}</pre>
                    </details>
                  ))}
                  <p className="slot-line">
                    Slot held: <strong>{item.slot_held ? "Yes" : "No — until you approve"}</strong>
                  </p>
                  <div className="approval-actions">
                    <button
                      type="button"
                      className="send"
                      disabled={busy}
                      onClick={() => onApprove(item.id)}
                    >
                      Approve and send
                    </button>
                    <button
                      type="button"
                      className="ghost-btn"
                      disabled={busy}
                      onClick={() => onReject(item.id)}
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </section>
          ) : null}

          {selected ? (
            <article className="bubble user">
              <p className="message-meta">Inbound</p>
              {selected.body}
            </article>
          ) : queue.length === 0 ? (
            <div className="empty">
              <p>Pick a message in the left inbox, or add one with Add inbound message.</p>
            </div>
          ) : null}

          {lastResult && selected ? (
            <article className="bubble assistant">
              <p className="message-meta">Clerk</p>
              <p>{lastResult.message}</p>
              {lastResult.auto_reply_text ? (
                <blockquote className="auto-sent">{lastResult.auto_reply_text}</blockquote>
              ) : null}
            </article>
          ) : null}
        </div>
      </main>

      <aside className="panel sources">
        <div className="pane-head">
          <p className="section-label">Sent</p>
          <button
            type="button"
            className="pane-collapse"
            aria-label={sentCollapsed ? "Show sent panel" : "Hide sent panel"}
            aria-expanded={!sentCollapsed}
            onClick={() => setSentCollapsed((open) => !open)}
          >
            {sentCollapsed ? "Show" : "Hide"}
          </button>
        </div>
        {outbox.length === 0 ? (
          <p className="muted-copy">Auto-replies and approved mail show here.</p>
        ) : (
          <div className="stack">
            {outbox.map((item) => (
              <div key={item.id} className="source-card">
                <header>
                  <strong>{kindLabel(item.kind)}</strong>
                  <span className="score">{new Date(item.sent_at).toLocaleString()}</span>
                </header>
                {item.to_email ? <p className="out-subject">To: {item.to_email}</p> : null}
                {item.subject ? <p className="out-subject">{item.subject}</p> : null}
                <p>{item.body}</p>
                {item.delivered ? (
                  <p className="pill ok">Delivered via SMTP</p>
                ) : item.delivery_error ? (
                  <p className="muted-copy">{item.delivery_error}</p>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}
