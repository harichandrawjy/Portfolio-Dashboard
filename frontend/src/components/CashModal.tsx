import { Trash, Warning } from "@phosphor-icons/react";
import { useEffect, useState } from "react";

import { api, type CashSummary } from "../api/client";
import { digitsOnly, fmtDate, fmtRp, groupDigits } from "../lib/format";
import {
  BinaryToggle,
  Button,
  ErrorNote,
  Field,
  Modal,
  Skeleton,
  useToast,
} from "./ui";

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
  const [deleting, setDeleting] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    api.cash(portfolioId).then(setSummary, () => setSummary(null));
  }, [portfolioId]);

  const removeFlow = async (flowId: string) => {
    setError(null);
    setDeleting(flowId);
    try {
      await api.deleteCashFlow(portfolioId, flowId);
      setSummary(await api.cash(portfolioId));
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDeleting(null);
    }
  };

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
      toast(
        `${type === "DEPOSIT" ? "Deposited" : "Withdrew"} ${fmtRp(amountNum)}.`,
      );
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
        <div className="flex items-baseline justify-between bg-panel-2 px-3 py-2.5">
          <span className="text-[13px] text-ink-2">Available</span>
          {summary === null ? (
            <Skeleton className="h-5 w-28" />
          ) : (
            <span className="tnum text-[19px] font-bold text-ink">
              {fmtRp(summary.balance)}
            </span>
          )}
        </div>

        {/* The balance only counts trades on or after the first cash flow.
            Without saying so, a portfolio funded after its buys reports cash
            those buys already spent. */}
        {summary && summary.uncounted_trades > 0 && summary.first_flow_date && (
          <p className="flex items-start gap-2 bg-warn/10 px-3 py-2 text-xs leading-relaxed text-warn ring-1 ring-warn/25">
            <Warning size={14} weight="light" className="mt-[2px] shrink-0" />
            <span>
              {summary.uncounted_trades} transaction
              {summary.uncounted_trades > 1 ? "s" : ""} dated before{" "}
              {fmtDate(summary.first_flow_date)}{" "}
              {summary.uncounted_trades > 1 ? "are" : "is"} not counted in this
              balance. Backdate your first deposit to before them to include
              their cost.
            </span>
          </p>
        )}

        <BinaryToggle
          label="Cash flow type" value={type}
          onChange={setType}
          options={[
            { value: "DEPOSIT", label: "Deposit" },
            { value: "WITHDRAW", label: "Withdraw" },
          ]}
        />

        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-2">
            <Field
              label="Amount (Rp)" type="text" inputMode="numeric" className="" value={groupDigits(amount)}
              onChange={(e) => setAmount(digitsOnly(e.target.value))}
              placeholder="10.000.000" hint={
                type === "WITHDRAW" && summary
                  ? `up to ${fmtRp(summary.balance)}`
                  : undefined
              }
              autoFocus
            />
            {type === "WITHDRAW" && summary !== null && summary.balance > 0 && (
              <button
                type="button" onClick={() => setAmount(String(summary.balance))}
                className="w-max text-xs text-ink-2 underline underline-offset-2 outline-none transition-colors hover:text-ink focus-visible:ring-2 focus-visible:ring-accent"
              >
                Withdraw everything
              </button>
            )}
          </div>
          <Field
            label="Date" type="date" value={date}
            max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => setDate(e.target.value)}
            hint={
              type === "DEPOSIT"
                ? "backdate to before your first trade to fund history"
                : undefined
            }
          />
        </div>

        <Field
          label="Note (optional)" value={note}
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
                <li key={f.id} className="flex items-center gap-3 text-[13px]">
                  {/* the label names the kind; the colour belongs to the
                      signed amount, which is what green and red mean here */}
                  <span className="w-16 shrink-0 text-xs font-medium text-ink-2">
                    {f.type === "DEPOSIT" ? "Deposit" : "Withdraw"}
                  </span>
                  <span
                    className={`tnum font-semibold ${
                      f.type === "DEPOSIT" ? "text-pos" : "text-neg"
                    }`}
                  >
                    {(f.type === "DEPOSIT" ? "+" : "-") + fmtRp(f.amount)}
                  </span>
                  <span className="ml-auto shrink-0 text-xs text-ink-3">
                    {fmtDate(f.occurred_at)}
                  </span>
                  <button
                    onClick={() => removeFlow(f.id)}
                    disabled={deleting === f.id}
                    className="shrink-0 p-1 text-ink-3 outline-none transition-colors hover:bg-neg/10 hover:text-neg focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-40" aria-label={`Delete ${f.type.toLowerCase()} of ${fmtRp(f.amount)}`}
                  >
                    <Trash size={13} weight="light" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Modal>
  );
}
