import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export function LoginPage(): React.ReactElement {
  const { login, isAuthenticated } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const from = (loc.state as { from?: string } | null)?.from ?? "/";
  const registered = (loc.state as { registered?: boolean } | null)?.registered;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) return <Navigate to={from} replace />;

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <h1 className="text-page text-slate-900">Sign in</h1>
      {registered && (
        <div
          className="mt-4 rounded border border-success/30 bg-green-50 px-3 py-2 text-datalabel text-success"
          role="status"
        >
          Account created — sign in.
        </div>
      )}
      <form
        className="mt-6 space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setErr(null);
          setLoading(true);
          try {
            await login(email, password);
            nav(from, { replace: true });
          } catch {
            setErr("Invalid email or password.");
          } finally {
            setLoading(false);
          }
        }}
      >
        <div>
          <label className="text-datalabel text-muted" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="text-datalabel text-muted" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {err && <p className="text-datalabel text-danger">{err}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-accent py-2 text-white disabled:opacity-60"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="mt-4 text-datalabel text-muted">
        No account?{" "}
        <Link className="text-accent hover:underline" to="/register">
          Register
        </Link>
      </p>
    </div>
  );
}
