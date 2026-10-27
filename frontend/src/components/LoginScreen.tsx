type LoginScreenProps = {
  password: string;
  error: string | null;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
};

export function LoginScreen({
  password,
  error,
  onPasswordChange,
  onSubmit,
}: LoginScreenProps) {
  return (
    <div className="login-screen">
      <form className="panel login-card" onSubmit={onSubmit}>
        <div className="brand">
          <strong>CLERK</strong>
          <span>Cape Town Physio · owner sign-in</span>
        </div>
        <p className="login-copy">
          Agreed replies can send automatically. Bookings and outbound email stay here until
          you approve them against the published pages.
        </p>
        <label>
          Owner password
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
