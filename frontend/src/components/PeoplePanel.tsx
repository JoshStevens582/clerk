import { useEffect, useState } from "react";

import {
  clearStaffMfa,
  createStaffUser,
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
  const [showAddStaff, setShowAddStaff] = useState(false);
  const [newStaff, setNewStaff] = useState({
    username: "",
    password: "",
    role: "staff" as "staff" | "manager",
    email: "",
  });

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
          Add staff accounts, change roles, disable accounts, or clear authenticators.
          Signed in as {signedInUsername}.
        </p>
        <button type="button" className="ghost" onClick={onBack}>
          Back to desk
        </button>
      </header>
      {error ? <p className="error banner">{error}</p> : null}
      {notice ? <p className="login-copy">{notice}</p> : null}
      <button
        type="button"
        className="new-chat"
        onClick={() => setShowAddStaff((open) => !open)}
      >
        {showAddStaff ? "Cancel" : "Add staff account"}
      </button>
      {showAddStaff ? (
        <form
          className="add-staff-form"
          onSubmit={(event) => {
            event.preventDefault();
            void runAdmin(async () => {
              const username = newStaff.username.trim().toLowerCase();
              await createStaffUser({
                username,
                password: newStaff.password,
                role: newStaff.role,
                email: newStaff.email.trim() || null,
              });
              setNewStaff({ username: "", password: "", role: "staff", email: "" });
              setShowAddStaff(false);
              setNotice(
                `Account ${username} created. They sign in here with that password and should change it under Security.`,
              );
            });
          }}
        >
          <label>
            Username (lowercase letters, numbers, - or _)
            <input
              required
              pattern="[a-z0-9_-]+"
              minLength={2}
              value={newStaff.username}
              onChange={(e) => setNewStaff({ ...newStaff, username: e.target.value })}
            />
          </label>
          <label>
            Temporary password (min 8 characters)
            <input
              required
              type="password"
              minLength={8}
              value={newStaff.password}
              onChange={(e) => setNewStaff({ ...newStaff, password: e.target.value })}
            />
          </label>
          <label>
            Role
            <select
              value={newStaff.role}
              onChange={(e) =>
                setNewStaff({
                  ...newStaff,
                  role: e.target.value as "staff" | "manager",
                })
              }
            >
              <option value="staff">Staff (desk only)</option>
              <option value="manager">Manager (People + desk)</option>
            </select>
          </label>
          <label>
            Email (optional — for password reset)
            <input
              type="email"
              value={newStaff.email}
              onChange={(e) => setNewStaff({ ...newStaff, email: e.target.value })}
            />
          </label>
          <button type="submit" className="send" disabled={busy}>
            Create account
          </button>
        </form>
      ) : null}
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
