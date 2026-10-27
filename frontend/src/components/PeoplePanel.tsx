import { useEffect, useState } from "react";

import { clearStaffMfa, fetchStaffUsers, type StaffAdminUser } from "../api";

type PeoplePanelProps = {
  signedInUsername: string;
  onBack: () => void;
};

export function PeoplePanel({ signedInUsername, onBack }: PeoplePanelProps) {
  const [people, setPeople] = useState<StaffAdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setPeople(await fetchStaffUsers());
  }

  useEffect(() => {
    void refresh().catch((err) => {
      setError(err instanceof Error ? err.message : "Could not load staff.");
    });
  }, []);

  async function onClearAuthenticator(username: string) {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await clearStaffMfa(username);
      setNotice(`Authenticator cleared for ${username}. They sign in with password only until they turn MFA on again.`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not clear authenticator.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel people-panel-page">
      <header className="chat-header">
        <h1>People</h1>
        <p>
          Managers can clear a locked-out staff member&apos;s authenticator (same as Atlas admin).
          Signed in as {signedInUsername}.
        </p>
        <button type="button" className="ghost" onClick={onBack}>
          Back to desk
        </button>
      </header>
      {error ? <p className="error banner">{error}</p> : null}
      {notice ? <p className="login-copy">{notice}</p> : null}
      <div className="people-list">
        {people.map((person) => (
          <article className="people-row" key={person.username}>
            <div>
              <strong>{person.username}</strong>
              <span>
                {person.role}
                {person.email ? ` · ${person.email}` : ""}
                {person.mfa_enabled ? " · authenticator on" : ""}
              </span>
            </div>
            <div className="people-actions">
              {person.username === signedInUsername ? (
                <span className="pill ok">you</span>
              ) : person.mfa_enabled ? (
                <button
                  type="button"
                  className="pill"
                  disabled={busy}
                  onClick={() => void onClearAuthenticator(person.username)}
                >
                  Clear authenticator
                </button>
              ) : (
                <span className="pill">no MFA</span>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
