type LoginScreenProps = {
  username: string;
  password: string;
  mfaCode: string;
  mfaStep: boolean;
  error: string | null;
  onUsernameChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onMfaCodeChange: (value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
  onBackFromMfa: () => void;
};

export function LoginScreen({
  username,
  password,
  mfaCode,
  mfaStep,
  error,
  onUsernameChange,
  onPasswordChange,
  onMfaCodeChange,
  onSubmit,
  onBackFromMfa,
}: LoginScreenProps) {
  return (
    <div className="login-screen">
      <form className="panel login-card" onSubmit={onSubmit}>
        <div className="brand">
          <strong>CLERK</strong>
          <span>Cape Town Physio · staff sign-in</span>
        </div>
        <p className="login-copy">
          Reception and managers use Clerk to approve bookings and outbound email. Agreed
          short replies still send automatically when policy allows.
        </p>
        {mfaStep ? (
          <>
            <p className="login-copy">
              Enter the 6-digit code from your authenticator app, or a recovery code.
            </p>
            <label>
              Authenticator code
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={mfaCode}
                onChange={(e) => onMfaCodeChange(e.target.value)}
                placeholder="123456"
              />
            </label>
            <button type="submit" className="send">
              Verify and sign in
            </button>
            <button type="button" className="ghost" onClick={onBackFromMfa}>
              Back
            </button>
          </>
        ) : (
          <>
            <label>
              Username
              <input
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => onUsernameChange(e.target.value)}
                placeholder="e.g. reception"
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => onPasswordChange(e.target.value)}
                placeholder="Password"
              />
            </label>
            <button type="submit" className="send">
              Sign in
            </button>
          </>
        )}
        {error ? <p className="error">{error}</p> : null}
      </form>
    </div>
  );
}
