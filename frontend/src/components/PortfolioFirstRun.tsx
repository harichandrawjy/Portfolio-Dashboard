import { Check } from "@phosphor-icons/react";
import { useState } from "react";

import { api } from "../api/client";
import { digitsOnly, fmtRp, groupDigits } from "../lib/format";
import { Button, ErrorNote, Field, Panel } from "./ui";

/** Sensible starting deposits for a mock portfolio, in rupiah. */
const QUICK_AMOUNTS = [10_000_000, 50_000_000, 100_000_000];

/**
 * A new portfolio has nothing to chart, allocate or total, and its primary
 * action cannot succeed: every buy is paid for from cash. Rather than four
 * panels each announcing their own emptiness, this one panel states the
 * enforced order — fund, then trade — and does the funding step inline.
 */
export function PortfolioFirstRun({
  portfolioId,
  cashBalance,
  funded,
  onChanged,
  onAddTransaction,
}: {
  portfolioId: string;
  cashBalance: number;
  /** the ledger has cash in it, so buying is unblocked */
  funded: boolean;
  onChanged: () => void;
  onAddTransaction: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [amount, setAmount] = useState("");
  // Dating the opening deposit matters more here than anywhere else in the
  // app: cash only funds trades executed on or after the first cash flow, so
  // someone recording history has to be able to put the deposit before their
  // oldest buy — otherwise those buys are silently left out of the balance.
  const [date, setDate] = useState(today);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const amountNum = parseInt(amount, 10);
  const amountOk = Number.isFinite(amountNum) && amountNum >= 1;
  const dateOk = date !== "" && date <= today;

  const deposit = async () => {
    if (!amountOk) {
      setError("Enter an amount of at least Rp 1.");
      return;
    }
    if (!dateOk) {
      setError("Pick a deposit date on or before today.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await api.addCashFlow(portfolioId, {
        type: "DEPOSIT",
        amount: amountNum,
        occurred_at: date,
        note: null,
      });
      setAmount("");
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel className="px-6 py-6 sm:px-8 sm:py-7">
      <h2 className="w-condensed text-[34px] font-extrabold uppercase leading-[0.92] tracking-[-0.02em] text-ink">
        {funded ? "Ready to trade" : "Fund this portfolio to begin"}
      </h2>
      <p className="mt-2 max-w-[62ch] text-[13px] leading-relaxed text-ink-2">
        {funded ? (
          <>
            <span className="tnum font-semibold text-ink">
              {fmtRp(cashBalance)}
            </span>{" "}
            is available. Record a buy and the rest of this page fills in:
            market value, unrealized P&amp;L, allocation and performance
            against the IHSG.
          </>
        ) : (
          <>
            Arus works like a brokerage account: a buy is paid for out of cash,
            so a deposit comes first. If you are recording trades that already
            happened, date the deposit before the oldest one. Only trades on or
            after your first cash flow count towards the balance.
          </>
        )}
      </p>

      {!funded && (
        <div className="mt-5 max-w-xl">
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_12rem]">
            <div>
              <label
                htmlFor="first-deposit"
                className="w-wide text-[11px] font-bold uppercase tracking-[0.12em] text-ink-2"
              >
                Opening deposit
              </label>
              {/* the Field idiom, hand-built because of the Rp prefix: filled
                  square, no resting border, edge only on focus */}
              <div className="mt-2 flex items-center bg-panel-2 px-3 py-2.5 ring-1 ring-transparent transition-shadow focus-within:bg-panel focus-within:ring-2 focus-within:ring-accent">
                <span className="mr-1 text-[13px] text-ink-3">Rp</span>
                <input
                  id="first-deposit" inputMode="numeric" value={groupDigits(amount)}
                  onChange={(e) => {
                    setAmount(digitsOnly(e.target.value));
                    setError(null);
                  }}
                  placeholder="10.000.000" className="tnum w-full min-w-0 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-3"
                />
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2">
                {QUICK_AMOUNTS.map((a) => (
                  <button
                    key={a}
                    type="button" onClick={() => {
                      setAmount(String(a));
                      setError(null);
                    }}
                    className="tnum press px-2 py-1 text-xs text-ink-3 outline-none ring-1 ring-line hover:text-ink hover:ring-line-2 focus-visible:ring-2 focus-visible:ring-accent"
                  >
                    {fmtRp(a)}
                  </button>
                ))}
              </div>
            </div>

            <Field
              label="Date" type="date" value={date}
              // a deposit cannot land in the future; the ledger is a record
              max={today}
              onChange={(e) => {
                setDate(e.target.value);
                setError(null);
              }}
              hint="Back-date to before your oldest buy."
            />
          </div>

          <div className="mt-4">
            <Button onClick={deposit} busy={busy} disabled={!amountOk || !dateOk}>
              Record deposit
            </Button>
          </div>

          {error && (
            <div className="mt-3">
              <ErrorNote message={error} />
            </div>
          )}
        </div>
      )}

      {funded && (
        <div className="mt-5">
          <Button onClick={onAddTransaction}>Record your first buy</Button>
        </div>
      )}

      {/* the enforced order, drawn as the current: cash flows into trades */}
      {/* capped: stretched across a 1200px panel the connector reads as a
          stranded hairline rather than one sequence */}
      <ol className="mt-7 flex max-w-xl flex-col gap-3 border-t border-line pt-5 sm:flex-row sm:items-center sm:gap-4">
        <Step n={1} label="Deposit cash" state={funded ? "done" : "current"} />
        <span
          aria-hidden
          className="hidden h-0.5 flex-1 sm:block" style={{
            background: funded
              ? "var(--color-accent)"
              : "rgb(10 12 16 / 0.15)",
          }}
        />
        <Step
          n={2}
          label="Record your first buy" state={funded ? "current" : "todo"}
        />
      </ol>
    </Panel>
  );
}

function Step({
  n,
  label,
  state,
}: {
  n: number;
  label: string;
  state: "done" | "current" | "todo";
}) {
  const marker =
    state === "done"
      ? "bg-accent text-on-accent"
      : state === "current"
        ? "bg-panel text-accent ring-2 ring-accent"
        : "bg-panel text-ink-3 ring-1 ring-line-2";
  return (
    <li className="flex shrink-0 items-center gap-2.5">
      <span
        className={`tnum flex h-6 w-6 items-center justify-center text-[11px] font-bold ${marker}`}
      >
        {state === "done" ? <Check size={13} weight="bold" /> : n}
      </span>
      <span
        className={`text-[13px] ${state === "todo" ? "text-ink-3" : "font-medium text-ink"}`}
      >
        {label}
      </span>
      {state === "done" && <span className="sr-only">— done</span>}
    </li>
  );
}
