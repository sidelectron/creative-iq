import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export function RegisterPage(): React.ReactElement {
  const { register, isAuthenticated } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fullName, setFullName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) return <Navigate to="/" replace />;

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <h1 className="text-page text-slate-900">Create account</h1>
      <form
        className="mt-6 space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setErr(null);
          if (password !== confirm) {
            setErr("Passwords do not match.");
            return;
          }
          if (password.length < 8) {
            setErr("Password must be at least 8 characters.");
            return;
          }
          setLoading(true);
          try {
            await register({ email, password, full_name: fullName });
            nav("/login", { replace: true, state: { registered: true } });
          } catch (ex: unknown) {
            const d = (ex as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            setErr(typeof d === "string" ? d : "Registration failed.");
          } finally {
            setLoading(false);
          }
        }}
      >
        <div>
          <label className="text-datalabel text-muted" htmlFor="fn">
            Full name
          </label>
          <input
            id="fn"
            required
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>
        <div>
          <label className="text-datalabel text-muted" htmlFor="em">
            Email
          </label>
          <input
            id="em"
            type="email"
            required
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="text-datalabel text-muted" htmlFor="pw">
            Password
          </label>
          <input
            id="pw"
            type="password"
            required
            minLength={8}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div>
          <label className="text-datalabel text-muted" htmlFor="pw2">
            Confirm password
          </label>
          <input
            id="pw2"
            type="password"
            required
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
        {err && <p className="text-datalabel text-danger">{err}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-accent py-2 text-white disabled:opacity-60"
        >
          {loading ? "Creating…" : "Register"}
        </button>
      </form>
      <p className="mt-4 text-datalabel text-muted">
        <Link className="text-accent hover:underline" to="/login">
          Back to login
        </Link>
      </p>
    </div>
  );
}
