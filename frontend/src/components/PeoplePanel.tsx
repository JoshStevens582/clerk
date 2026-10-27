import { useEffect, useState } from "react";

import {
  clearStaffMfa,
  fetchStaffUsers,
  setStaffUserDisabled,
  setStaffUserRole,
  type StaffAdminUser,
} from "../api";

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

  async function runAdmin(action: () => Promise<void>) {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That change could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel people-panel-page">
      <header className="chat-header">
        <h1>People</h1>
        <p>
          Managers can promote or demote staff, disable accounts, or clear a locked-out
          authenticator — same idea as Atlas admin People. Signed in as {signedInUsername}.
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
                {!person.active ? " · disabled" : ""}
                {person.email ? ` · ${person.email}` : ""}
                {person.mfa_enabled ? " · authenticator on" : ""}
              </span>
            </div>
            <div className="people-actions">
              {person.username === signedInUsername ? (
                <span className="pill ok">you</span>
              ) : (
                <>
                  <button
                    type="button"
                    className="pill"
                    disabled={busy}
                    onClick={() =>
                      void runAdmin(async () => {
                        const nextRole = person.role === "manager" ? "staff" : "manager";
                        await setStaffUserRole(person.username, nextRole);
                        setNotice(
                          `${person.username} is now ${nextRole === "manager" ? "a manager" : "staff"}.`,
                        );
                      })
                    }
                  >
                    {person.role === "manager" ? "Make staff" : "Make manager"}
                  </button>
                  <button
                    type="button"
                    className="pill"
                    disabled={busy}
                    onClick={() =>
                      void runAdmin(async () => {
                        const disable = person.active;
                        await setStaffUserDisabled(person.username, disable);
                        setNotice(
                          disable
                            ? `${person.username} is disabled and signed out.`
                            : `${person.username} is enabled again.`,
                        );
                      })
                    }
                  >
                    {person.active ? "Disable" : "Enable"}
                  </button>
                  {person.mfa_enabled ? (
                    <button
                      type="button"
                      className="pill"
                      disabled={busy}
                      onClick={() =>
                        void runAdmin(async () => {
                          await clearStaffMfa(person.username);
                          setNotice(
                            `Authenticator cleared for ${person.username}. They sign in with password only until they turn MFA on again.`,
                          );
                        })
                      }
                    >
                      Clear authenticator
                    </button>
                  ) : null}
                </>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
