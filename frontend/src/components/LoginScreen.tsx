type LoginScreenProps = {
  username: string;
  password: string;
  error: string | null;
  onUsernameChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
};

export function LoginScreen({
  username,
  password,
  error,
  onUsernameChange,
  onPasswordChange,
  onSubmit,
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
        {error ? <p className="error">{error}</p> : null}
      </form>
    </div>
  );
}
