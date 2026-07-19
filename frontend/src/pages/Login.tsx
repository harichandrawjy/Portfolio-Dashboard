import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth";
import { Button, ErrorNote, Field } from "../components/ui";

type Mode = "login" | "register";

export function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, displayName || undefined);
      navigate("/", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-[100dvh] lg:grid-cols-[1.1fr_1fr]">
      {/* ------------------------------------------- brand half */}
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-line p-12 lg:flex">
        <p className="text-[15px] font-semibold tracking-tight text-ink">
          Arus<span className="text-accent">.</span>
        </p>

        <div className="rise" style={{ "--rise": 1 } as React.CSSProperties}>
          <h1 className="text-6xl font-semibold leading-[1.04] tracking-tight text-ink xl:text-7xl">
            Every lot,
            <br />
            accounted for.
          </h1>
          <p className="mt-6 max-w-[44ch] text-[15px] leading-relaxed text-ink-2">
            Mock IDX portfolios with honest analytics: time-weighted returns,
            drawdowns, and a benchmark that keeps score.
          </p>
        </div>

        <p className="tnum font-mono text-xs text-ink-3">
          963 IDX tickers · 5y daily bars · IHSG benchmark
        </p>
      </aside>

      {/* -------------------------------------------- form half */}
      <main className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <p className="mb-10 text-[15px] font-semibold tracking-tight text-ink lg:hidden">
            Arus<span className="text-accent">.</span>
          </p>

          <h2 className="text-2xl font-semibold tracking-tight text-ink">
            {mode === "login" ? "Sign in" : "Create an account"}
          </h2>

          <div className="mt-2 mb-8 flex gap-5 text-[13px]">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => {
                  setMode(m);
                  setError(null);
                }}
                className={
                  "border-b pb-1 outline-none transition-colors focus-visible:text-ink " +
                  (mode === m
                    ? "border-accent text-ink"
                    : "border-transparent text-ink-3 hover:text-ink-2")
                }
              >
                {m === "login" ? "Sign in" : "New account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="flex flex-col gap-4">
            {mode === "register" && (
              <Field
                label="Display name (optional)"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Andi"
                autoComplete="name"
              />
            )}
            <Field
              label="Email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
            <Field
              label="Password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              hint={mode === "register" ? "At least 8 characters" : undefined}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
            {error && <ErrorNote message={error} />}
            <Button type="submit" busy={busy} className="mt-2 w-full">
              {mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <p className="mt-6 text-xs text-ink-3">
            Mock portfolios only. No real money moves here.
          </p>
        </div>
      </main>
    </div>
  );
}
