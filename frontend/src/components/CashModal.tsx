import { useEffect, useState } from "react";

import { api, type CashSummary } from "../api/client";
import { fmtDate, fmtRp } from "../lib/format";
import { Button, ErrorNote, Field, Modal, Skeleton } from "./ui";

export function CashModal({
  portfolioId,
  onClose,
  onChanged,
}: {
  portfolioId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [summary, setSummary] = useState<CashSummary | null>(null);
  const [type, setType] = useState<"DEPOSIT" | "WITHDRAW">("DEPOSIT");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.cash(portfolioId).then(setSummary, () => setSummary(null));
  }, [portfolioId]);

  const submit = async () => {
    setError(null);
    const amountNum = parseInt(amount, 10);
    if (!Number.isFinite(amountNum) || amountNum < 1)
      return setError("Amount must be a positive whole-rupiah number.");
    setBusy(true);
    try {
      const updated = await api.addCashFlow(portfolioId, {
        type,
        amount: amountNum,
        occurred_at: date,
        note: note.trim() || null,
      });
      setSummary(updated);
      setAmount("");
      setNote("");
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Cash" onClose={onClose}>
      <div className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between rounded-[6px] bg-ink/[0.03] px-3 py-2.5 ring-1 ring-line">
          <span className="text-[13px] text-ink-2">Available</span>
          {summary === null ? (
            <Skeleton className="h-5 w-28" />
          ) : (
            <span className="tnum font-mono text-lg font-semibold text-ink">
              {fmtRp(summary.balance)}
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2">
          {(["DEPOSIT", "WITHDRAW"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={
                "rounded-[6px] py-2 text-sm font-semibold ring-1 transition-all duration-200 active:scale-[0.98] " +
                (type === t
                  ? t === "DEPOSIT"
                    ? "bg-pos/10 text-pos ring-pos/50"
                    : "bg-neg/10 text-neg ring-neg/50"
                  : "bg-panel text-ink-3 ring-line hover:text-ink-2")
              }
            >
              {t === "DEPOSIT" ? "Deposit" : "Withdraw"}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field
            label="Amount (Rp)"
            type="number"
            min={1}
            step={1}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="10000000"
            autoFocus
          />
          <Field
            label="Date"
            type="date"
            value={date}
            max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>

        <Field
          label="Note (optional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Monthly top-up"
        />

        {error && <ErrorNote message={error} />}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button onClick={submit} busy={busy}>
            {type === "DEPOSIT" ? "Record deposit" : "Record withdrawal"}
          </Button>
        </div>

        {summary !== null && summary.flows.length > 0 && (
          <div className="border-t border-line pt-3">
            <p className="mb-2 text-[13px] font-medium text-ink-2">Recent</p>
            <ul className="max-h-40 space-y-1.5 overflow-y-auto">
              {summary.flows.map((f) => (
                <li key={f.id} className="flex items-baseline gap-3 text-[13px]">
                  <span
                    className={`w-16 shrink-0 text-xs font-semibold ${
                      f.type === "DEPOSIT" ? "text-pos" : "text-neg"
                    }`}
                  >
                    {f.type === "DEPOSIT" ? "Deposit" : "Withdraw"}
                  </span>
                  <span className="tnum font-mono text-ink">
                    {(f.type === "DEPOSIT" ? "+" : "-") + fmtRp(f.amount)}
                  </span>
                  <span className="ml-auto shrink-0 text-xs text-ink-3">
                    {fmtDate(f.occurred_at)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Modal>
  );
}
