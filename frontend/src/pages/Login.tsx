import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth";
import { Button, ErrorNote, Field } from "../components/ui";

type Mode = "login" | "register";

// Both must be set for the demo entry to exist at all, so a private
// deployment never ships a shared account it did not ask for.
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL;
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD;
const DEMO_READY = Boolean(DEMO_EMAIL && DEMO_PASSWORD);

/** Fixed heights for the knockout column motif. Hand-set rather than random
 *  so the composition is stable across reloads — a Swiss plate is drawn, not
 *  generated. */
const COLUMNS = [
  18, 26, 22, 34, 30, 46, 38, 52, 44, 62, 54, 70, 58, 78, 66, 86, 74, 94, 82,
  100,
];

export function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);

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

  const signInAsDemo = async () => {
    if (!DEMO_EMAIL || !DEMO_PASSWORD) return;
    setError(null);
    setDemoBusy(true);
    try {
      await login(DEMO_EMAIL, DEMO_PASSWORD);
      navigate("/", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setDemoBusy(false);
    }
  };

  return (
    <div className="grid min-h-[100dvh] lg:grid-cols-[1.15fr_1fr]">
      {/* ─────────────────────────── brand: one flat field of the accent,
          knockout type, and the data motif drawn as a rising raster of
          columns. A band across the top on small screens, the full left
          column from lg. */}
      <aside className="field-wipe relative flex flex-col justify-between gap-10 overflow-hidden bg-accent px-6 py-8 text-on-accent lg:gap-0 lg:p-12">
        <p className="w-wide relative flex items-baseline gap-1.5 text-[19px] font-extrabold uppercase leading-none tracking-[0.16em]">
          Arus
          <span aria-hidden className="block h-2 w-2 bg-on-accent" />
        </p>

        <div className="relative">
          <div className="rule-draw mb-6 h-[3px] w-24 bg-on-accent lg:mb-10" />
          <h1 className="w-condensed text-[clamp(2.75rem,7vw,5.5rem)] font-extrabold uppercase leading-[0.88] tracking-[-0.03em]">
            Every lot
            <br />
            on the
            <br />
            record
          </h1>
          <p className="mt-6 max-w-[42ch] text-[15px] leading-relaxed text-on-accent/80">
            Mock IDX portfolios with honest analytics: time-weighted returns,
            drawdowns, and a benchmark that keeps score.
          </p>
        </div>

        {/* the raster: measured marks, not ornament — the same column
            language the portfolio cards use */}
        <div className="relative">
          <div
            className="flex h-20 items-end gap-[3px] lg:h-28" aria-hidden
          >
            {COLUMNS.map((h, i) => (
              <span
                key={i}
                className="min-w-0 flex-1 bg-on-accent" style={{ height: `${h}%`, opacity: 0.2 + (i / COLUMNS.length) * 0.75 }}
              />
            ))}
          </div>
          <dl className="mt-4 grid grid-cols-3 gap-4 border-t border-on-accent/30 pt-3 text-[11px] leading-tight">
            {[
              ["963", "IDX tickers"],
              ["5y", "daily bars"],
              ["IHSG", "benchmark"],
            ].map(([v, l]) => (
              <div key={l}>
                <dt className="sr-only">{l}</dt>
                <dd className="tnum text-[17px] font-bold leading-none">{v}</dd>
                <dd className="w-wide mt-1.5 uppercase tracking-[0.12em] text-on-accent">
                  {l}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </aside>

      {/* ─────────────────────────── form half */}
      <main className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          {/* the tabs below already say "Sign in"; the heading should say
              something rather than repeat the active tab's label */}
          <h2 className="w-condensed text-[34px] font-extrabold uppercase leading-[0.92] tracking-[-0.02em] text-ink">
            {mode === "login" ? "Sign in to your portfolios" : "Create an account"}
          </h2>

          <div className="mb-9 mt-5 flex gap-px bg-line">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                type="button" aria-pressed={mode === m}
                onClick={() => {
                  setMode(m);
                  setError(null);
                }}
                className={
                  "flex-1 py-2.5 text-[11px] font-bold uppercase tracking-[0.12em] leading-none " +
                  "outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent " +
                  (mode === m
                    ? "bg-ink text-bg"
                    : "bg-panel-2 text-ink-3 hover:text-ink")
                }
              >
                {m === "login" ? "Sign in" : "New account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="flex flex-col gap-4">
            {mode === "register" && (
              <Field
                label="Display name (optional)" value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Andi" autoComplete="name"
              />
            )}
            <Field
              label="Email" type="email" required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com" autoComplete="email"
            />
            <Field
              label="Password" type="password" required
              // only a new password has to clear the length bar
              minLength={mode === "register" ? 8 : undefined}
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

          {DEMO_READY && (
            <div className="mt-8 border-t border-line-2 pt-6">
              <Button
                variant="ghost" className="w-full" busy={demoBusy}
                onClick={signInAsDemo}
              >
                Explore the demo portfolio
              </Button>
              <p className="mt-3 text-xs leading-relaxed text-ink-3">
                Two years of recorded IDX trades, already funded. Shared by
                everyone who opens this demo, so treat it as a sandbox.
              </p>
            </div>
          )}

          <p className="w-wide mt-8 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-3">
            Mock portfolios only — no real money moves here
          </p>
        </div>
      </main>
    </div>
  );
}
