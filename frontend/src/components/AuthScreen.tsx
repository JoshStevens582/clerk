import { useEffect, useState } from "react";

import {
  completeMfaLogin,
  fetchDemoStatus,
  forgotPassword,
  login,
  loginDemo,
  resetPassword,
  type StaffUser,
} from "../api";

type AuthMode = "login" | "forgot" | "reset" | "mfa";

type AuthScreenProps = {
  onSignedIn: (user: StaffUser) => void;
};

export function AuthScreen({ onSignedIn }: AuthScreenProps) {
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [mfaToken, setMfaToken] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [forgotNotice, setForgotNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demoAvailable, setDemoAvailable] = useState(false);

  useEffect(() => {
    void fetchDemoStatus()
      .then(setDemoAvailable)
      .catch(() => setDemoAvailable(false));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("reset_token");
    if (token) {
      setResetToken(token);
      setAuthMode("reset");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  function heading(): string {
    if (authMode === "forgot") return "Reset your password";
    if (authMode === "reset") return "Choose a new password";
    if (authMode === "mfa") return "Authenticator code";
    return "Staff sign-in";
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (authMode === "forgot") {
        const result = await forgotPassword(username.trim());
        setForgotNotice(result.message);
        if (result.dev_reset_token) {
          setResetToken(result.dev_reset_token);
          setAuthMode("reset");
          setForgotNotice(`${result.message} (Dev token loaded — paste not needed.)`);
        }
        return;
      }
      if (authMode === "reset") {
        await resetPassword(resetToken.trim(), password.trim());
        setAuthMode("login");
        setPassword("");
        setForgotNotice("Password updated. Sign in with your new password.");
        return;
      }
      if (authMode === "mfa") {
        const user = await completeMfaLogin(mfaToken, mfaCode.trim());
        onSignedIn(user);
        return;
      }
      const result = await login(username.trim(), password);
      if (result.mfaRequired && result.mfaToken) {
        setMfaToken(result.mfaToken);
        setMfaCode("");
        setPassword("");
        setAuthMode("mfa");
        return;
      }
      onSignedIn(result.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-screen app--clerk">
      <form className="panel login-card" onSubmit={(e) => void onSubmit(e)}>
        <div className="brand">
          <img src="/brand/clerk-mark.svg" alt="" className="brand-mark" width={40} height={40} />
          <div className="brand-text">
            <strong>CLERK</strong>
            <span>{heading()}</span>
          </div>
        </div>
        <p className="product-audience">For staff · inbox automation</p>
        {authMode === "login" ? (
          <p className="login-copy">
            Try the live demo with one click, or sign in with the staff account your clinic was
            given. Demo visitors only see sample patient mail — nothing real is emailed out.
          </p>
        ) : null}
        {authMode === "login" || authMode === "forgot" ? (
          <label>
            Username
            <input
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>
        ) : null}
        {authMode === "reset" ? (
          <label>
            Reset token
            <input value={resetToken} onChange={(e) => setResetToken(e.target.value)} />
          </label>
        ) : null}
        {authMode === "mfa" ? (
          <>
            <p className="login-copy">
              Enter the 6-digit code from Google or Microsoft Authenticator, or a saved recovery
              code.
            </p>
            <label>
              Code
              <input
                inputMode="numeric"
                autoComplete="one-time-code"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
              />
            </label>
          </>
        ) : null}
        {authMode !== "forgot" && authMode !== "mfa" ? (
          <label>
            Password
            <input
              type="password"
              autoComplete={authMode === "reset" ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
        ) : null}
        {authMode === "forgot" ? (
          <p className="login-copy">
            Enter your username. If your account has a reset email on file, we send a link.
          </p>
        ) : null}
        {forgotNotice ? <p className="login-copy">{forgotNotice}</p> : null}
        {error ? <p className="error">{error}</p> : null}
        <button type="submit" className="send" disabled={busy}>
          {authMode === "forgot"
            ? "Send reset link"
            : authMode === "reset"
              ? "Update password"
              : authMode === "mfa"
                ? "Confirm code"
                : "Sign in"}
        </button>
        {authMode === "login" && demoAvailable ? (
          <button
            type="button"
            className="ghost-btn"
            disabled={busy}
            onClick={() => {
              setError(null);
              setBusy(true);
              void loginDemo()
                .then(onSignedIn)
                .catch((err: unknown) => {
                  setError(err instanceof Error ? err.message : "Demo login failed");
                })
                .finally(() => setBusy(false));
            }}
          >
            Continue as demo visitor
          </button>
        ) : null}
        {authMode === "login" ? (
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setError(null);
              setForgotNotice(null);
              setAuthMode("forgot");
            }}
          >
            Forgot password?
          </button>
        ) : null}
        {authMode !== "login" ? (
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setError(null);
              setAuthMode("login");
            }}
          >
            Back to sign-in
          </button>
        ) : null}
      </form>
    </div>
  );
}
