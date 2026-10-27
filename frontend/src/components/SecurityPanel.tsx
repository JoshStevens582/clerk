import { useState } from "react";

import {
  changePassword,
  confirmMfaSetup,
  disableMfa,
  regenerateRecoveryCodes,
  startMfaSetup,
  updateEmail,
  type MfaSetup,
  type StaffUser,
} from "../api";
import { copyRecoveryCodes, downloadRecoveryCodes } from "../mfaRecoveryCodes";

type SecurityPanelProps = {
  user: StaffUser;
  mfaEnabled: boolean;
  onBack: () => void;
  onMfaEnabledChange: (enabled: boolean) => void;
  onUserUpdate: (user: StaffUser) => void;
};

export function SecurityPanel({
  user,
  mfaEnabled,
  onBack,
  onMfaEnabledChange,
  onUserUpdate,
}: SecurityPanelProps) {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [email, setEmail] = useState(user.email ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [mfaPassword, setMfaPassword] = useState("");
  const [mfaActionCode, setMfaActionCode] = useState("");
  const [mfaSetup, setMfaSetup] = useState<MfaSetup | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [recoveryAck, setRecoveryAck] = useState(false);
  const [recoveryExported, setRecoveryExported] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSaveEmail() {
    setError(null);
    setBusy(true);
    try {
      const updated = await updateEmail(email.trim());
      onUserUpdate(updated);
      setNotice("Reset email saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save email.");
    } finally {
      setBusy(false);
    }
  }

  async function onChangePassword() {
    setError(null);
    setBusy(true);
    try {
      const message = await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setNotice(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password change failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onStartMfa() {
    setError(null);
    setBusy(true);
    try {
      setMfaSetup(await startMfaSetup(mfaPassword));
      setMfaPassword("");
      setMfaActionCode("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start MFA setup.");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirmMfa() {
    setError(null);
    setBusy(true);
    try {
      const codes = await confirmMfaSetup(mfaActionCode.trim());
      setRecoveryCodes(codes);
      setMfaSetup(null);
      setMfaActionCode("");
      onMfaEnabledChange(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Code did not match.");
    } finally {
      setBusy(false);
    }
  }

  async function onRegenerateCodes() {
    setError(null);
    setBusy(true);
    try {
      const codes = await regenerateRecoveryCodes(mfaPassword, mfaActionCode.trim());
      setRecoveryCodes(codes);
      setMfaPassword("");
      setMfaActionCode("");
      setNotice("New recovery codes issued.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not regenerate codes.");
    } finally {
      setBusy(false);
    }
  }

  async function onDisableMfa() {
    setError(null);
    setBusy(true);
    try {
      const message = await disableMfa(mfaPassword, mfaActionCode.trim());
      onMfaEnabledChange(false);
      setMfaPassword("");
      setMfaActionCode("");
      setNotice(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not turn MFA off.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel security-panel">
      <header className="chat-header">
        <h1>Security</h1>
        <p>Password, reset email, and authenticator — same pattern as Atlas.</p>
        <button type="button" className="ghost" onClick={onBack}>
          Back to desk
        </button>
      </header>
      {error ? <p className="error banner">{error}</p> : null}
      {notice ? <p className="login-copy">{notice}</p> : null}

      <div className="mfa-setup">
        <h2 className="section-label">Password reset email</h2>
        <p className="login-copy">Required for &quot;Forgot password?&quot; to send you a link.</p>
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <button type="button" className="pill" disabled={busy || !email.includes("@")} onClick={() => void onSaveEmail()}>
          Save email
        </button>

        <h2 className="section-label">Change password</h2>
        <label>
          Current password
          <input
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />
        </label>
        <label>
          New password
          <input
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="send"
          disabled={busy || !currentPassword || newPassword.length < 8}
          onClick={() => void onChangePassword()}
        >
          Update password
        </button>

        {recoveryCodes ? (
          <>
            <p className="mfa-scan-warning">
              Save these recovery codes now. Clerk will not show them again.
            </p>
            <ul className="recovery-codes">
              {recoveryCodes.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <div className="recovery-actions">
              <button
                type="button"
                className="pill"
                onClick={() => {
                  void copyRecoveryCodes(recoveryCodes).then(() => setRecoveryExported(true));
                }}
              >
                Copy all
              </button>
              <button
                type="button"
                className="pill"
                onClick={() => {
                  downloadRecoveryCodes(recoveryCodes, user.username);
                  setRecoveryExported(true);
                }}
              >
                Download .txt
              </button>
            </div>
            <label className="recovery-ack">
              <input
                type="checkbox"
                checked={recoveryAck}
                onChange={(e) => setRecoveryAck(e.target.checked)}
              />
              <span>I saved these codes somewhere safe.</span>
            </label>
            <button
              type="button"
              className="send"
              disabled={!recoveryAck || !recoveryExported}
              onClick={() => {
                setRecoveryCodes(null);
                setRecoveryAck(false);
                setRecoveryExported(false);
              }}
            >
              Continue
            </button>
          </>
        ) : mfaSetup ? (
          <>
            <p className="mfa-scan-warning">
              Scan with Google or Microsoft Authenticator — not a generic QR app.
            </p>
            <img className="mfa-qr" src={mfaSetup.qr_data_uri} alt="Authenticator QR code" />
            <p className="mfa-secret">{mfaSetup.secret}</p>
            <label>
              Code from app
              <input
                inputMode="numeric"
                value={mfaActionCode}
                onChange={(e) => setMfaActionCode(e.target.value)}
              />
            </label>
            <button
              type="button"
              className="send"
              disabled={busy || mfaActionCode.trim().length < 6}
              onClick={() => void onConfirmMfa()}
            >
              Turn on authenticator
            </button>
          </>
        ) : mfaEnabled ? (
          <>
            <p className="login-copy">Authenticator is on for this account.</p>
            <label>
              Password
              <input
                type="password"
                value={mfaPassword}
                onChange={(e) => setMfaPassword(e.target.value)}
              />
            </label>
            <label>
              Authenticator or recovery code
              <input
                value={mfaActionCode}
                onChange={(e) => setMfaActionCode(e.target.value)}
              />
            </label>
            <button type="button" className="pill" disabled={busy} onClick={() => void onRegenerateCodes()}>
              New recovery codes
            </button>
            <button type="button" className="send" disabled={busy} onClick={() => void onDisableMfa()}>
              Turn off authenticator
            </button>
          </>
        ) : (
          <>
            <p className="login-copy">Add a second step after your password (recommended for managers).</p>
            <label>
              Password
              <input
                type="password"
                value={mfaPassword}
                onChange={(e) => setMfaPassword(e.target.value)}
              />
            </label>
            <button type="button" className="send" disabled={busy || !mfaPassword} onClick={() => void onStartMfa()}>
              Set up authenticator
            </button>
          </>
        )}
      </div>
    </section>
  );
}
