import type { HealthStatus, MessageResult, OutboxItem, QueueItem, StaffUser } from "../api";
import { INBOX, type InboxMessage } from "../inbox";
import { kindLabel } from "../labels";

type ClerkWorkspaceProps = {
  user: StaffUser;
  health: HealthStatus | null;
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
  onLogout: () => void;
};

export function ClerkWorkspace({
  user,
  health,
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
  onLogout,
}: ClerkWorkspaceProps) {
  const pending = queue.length;

  return (
    <div className="app">
      <aside className="panel sidebar">
        <div className="brand">
          <strong>CLERK</strong>
          <span>Inbox automation</span>
        </div>
        <p className="workspace-name">Cape Town Physio</p>
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
          <span className={`pill ${pending > 0 ? "warn" : "ok"}`}>
            {pending} awaiting approval
          </span>
        </div>
        <p className="section-label">Inbox</p>
        <div className="stack">
          {INBOX.map((message) => {
            const isActive = selected?.id === message.id;
            const handled = processedIds.has(message.id);
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
          })}
        </div>
        <button type="button" className="new-chat" onClick={onLogout}>
          Sign out
        </button>
        <p className="suite-links">
          <a href="https://counter.customchatandautomation.co.za" target="_blank" rel="noreferrer">
            Counter
          </a>
          {" · "}
          <a href="https://atlas.customchatandautomation.co.za" target="_blank" rel="noreferrer">
            Atlas
          </a>
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
              <h1>Inbox</h1>
              <p>Select a message to run Clerk on it.</p>
            </>
          )}
        </header>

        <div className="workspace-body">
          {error ? <p className="error banner">{error}</p> : null}

          {selected ? (
            <article className="bubble user">
              <p className="message-meta">Inbound</p>
              {selected.body}
            </article>
          ) : (
            <div className="empty">
              <p>New patient and client mail appears in the left column.</p>
            </div>
          )}

          {lastResult && selected ? (
            <article className="bubble assistant">
              <p className="message-meta">Clerk</p>
              <p>{lastResult.message}</p>
              {lastResult.auto_reply_text ? (
                <blockquote className="auto-sent">{lastResult.auto_reply_text}</blockquote>
              ) : null}
            </article>
          ) : null}

          {queue.length > 0 ? (
            <section className="approval-section">
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
        </div>
      </main>

      <aside className="panel sources">
        <p className="section-label">Sent</p>
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
                {item.subject ? <p className="out-subject">{item.subject}</p> : null}
                <p>{item.body}</p>
              </div>
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}
