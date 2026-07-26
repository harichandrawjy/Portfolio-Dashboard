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
      {/* ------------------------------------- brand half: a bold cobalt
          block with knockout type and a white current drawn on entry */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-accent p-12 text-white lg:flex">
        {/* the current: a rising market line that draws itself on entry */}
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full"
          viewBox="0 0 600 900"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden
        >
          <defs>
            <linearGradient id="arus-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#ffffff" stopOpacity="0.16" />
              <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="arus-line" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#ffffff" stopOpacity="0.35" />
              <stop offset="0.55" stopColor="#ffffff" stopOpacity="0.95" />
              <stop offset="1" stopColor="#ffffff" stopOpacity="0.6" />
            </linearGradient>
          </defs>
          <path
            d="M0 640 C 90 620 130 540 210 520 C 300 498 330 596 420 540 C 500 490 520 360 600 300 L 600 900 L 0 900 Z"
            fill="url(#arus-fill)"
          />
          <path
            d="M0 640 C 90 620 130 540 210 520 C 300 498 330 596 420 540 C 500 490 520 360 600 300"
            fill="none"
            stroke="url(#arus-line)"
            strokeWidth="2.5"
            strokeLinecap="round"
            pathLength={1}
            className="draw-in"
            style={{ filter: "drop-shadow(0 0 12px rgb(255 255 255 / 0.4))" }}
          />
        </svg>

        <p className="relative font-serif text-[22px] font-semibold text-white">
          Arus<span className="current-dot">.</span>
        </p>

        <div className="relative rise" style={{ "--rise": 1 } as React.CSSProperties}>
          <div className="mb-8 h-0.5 w-16 rounded-full bg-gradient-to-r from-white to-transparent" />
          <h1 className="font-serif text-6xl font-semibold leading-[1.06] text-white xl:text-7xl">
            Every lot,
            <br />
            in the current.
          </h1>
          <p className="mt-6 max-w-[44ch] text-[15px] leading-relaxed text-white/80">
            Mock IDX portfolios with honest analytics: time-weighted returns,
            drawdowns, and a benchmark that keeps score.
          </p>
        </div>

        <p className="tnum relative flex items-center gap-2 font-mono text-xs text-white/75">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-white current-dot" />
          963 IDX tickers · 5y daily bars · IHSG benchmark
        </p>
      </aside>

      {/* -------------------------------------------- form half */}
      <main className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <p className="mb-10 font-serif text-[22px] font-semibold text-ink lg:hidden">
            Arus<span className="current-dot text-accent">.</span>
          </p>

          <h2 className="font-serif text-3xl font-semibold text-ink">
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
