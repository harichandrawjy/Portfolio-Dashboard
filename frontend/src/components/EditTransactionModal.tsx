import { useState } from "react";

import { api, type Transaction, type TxnType } from "../api/client";
import { digitsOnly, fmtNum, fmtRp, groupDigits } from "../lib/format";
import { Button, ErrorNote, Field, Modal } from "./ui";

const SHARES_PER_LOT = 100;

/** Edit an existing transaction. The security is fixed (delete + re-add to
 *  change the ticker); the server re-validates the derived holdings/cash. */
export function EditTransactionModal({
  portfolioId,
  transaction,
  onClose,
  onSaved,
}: {
  portfolioId: string;
  transaction: Transaction;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [type, setType] = useState<TxnType>(transaction.type);
  const [lots, setLots] = useState(String(transaction.lots));
  const [price, setPrice] = useState(String(transaction.price_per_share));
  const [fee, setFee] = useState(String(transaction.fee));
  const [date, setDate] = useState(transaction.executed_at);
  const [note, setNote] = useState(transaction.note ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const lotsNum = parseInt(lots, 10);
  const priceNum = parseInt(price, 10);
  const feeNum = parseInt(fee || "0", 10);
  const lotsOk = Number.isFinite(lotsNum) && lotsNum >= 1;
  const priceOk = Number.isFinite(priceNum) && priceNum >= 1;
  const shares = lotsOk ? lotsNum * SHARES_PER_LOT : null;
  const total =
    lotsOk && priceOk
      ? lotsNum * SHARES_PER_LOT * priceNum +
        (type === "BUY" ? feeNum : -feeNum)
      : null;

  const submit = async () => {
    setError(null);
    if (!lotsOk) return setError("Lots must be a whole number of at least 1.");
    if (!priceOk)
      return setError("Price per share must be a positive whole-rupiah amount.");
    if (!Number.isFinite(feeNum) || feeNum < 0)
      return setError("Fee cannot be negative.");

    setBusy(true);
    try {
      await api.updateTransaction(portfolioId, transaction.id, {
        type,
        lots: lotsNum,
        price_per_share: priceNum,
        fee: feeNum,
        executed_at: date,
        note: note.trim() || null,
      });
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Edit transaction" onClose={onClose} wide>
      <div className="flex flex-col gap-4">
        {/* locked ticker */}
        <div className="flex items-center justify-between rounded-[6px] bg-ink/[0.03] px-3 py-2.5 ring-1 ring-line">
          <span className="text-[13px] text-ink-2">Ticker</span>
          <span className="font-mono text-sm font-semibold text-ink">
            {transaction.ticker}
          </span>
        </div>

        {/* BUY / SELL toggle */}
        <div className="grid grid-cols-2 gap-2">
          {(["BUY", "SELL"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={
                "rounded-[6px] py-2 text-sm font-semibold ring-1 transition-all duration-200 active:scale-[0.98] " +
                (type === t
                  ? t === "BUY"
                    ? "bg-pos/10 text-pos ring-pos/50"
                    : "bg-neg/10 text-neg ring-neg/50"
                  : "bg-panel text-ink-3 ring-line hover:text-ink-2")
              }
            >
              {t === "BUY" ? "Buy" : "Sell"}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field
            label="Lots"
            type="text"
            inputMode="numeric"
            className="font-mono"
            value={lots}
            onChange={(e) => setLots(digitsOnly(e.target.value))}
            hint={shares != null ? `= ${fmtNum(shares)} shares` : undefined}
          />
          <Field
            label="Price per share (Rp)"
            type="text"
            inputMode="numeric"
            className="font-mono"
            value={groupDigits(price)}
            onChange={(e) => setPrice(digitsOnly(e.target.value))}
          />
          <Field
            label="Fee (Rp)"
            type="text"
            inputMode="numeric"
            className="font-mono"
            value={groupDigits(fee)}
            onChange={(e) => setFee(digitsOnly(e.target.value))}
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
          placeholder="Why this trade?"
        />

        <div className="flex items-baseline justify-between border-t border-line pt-3">
          <span className="text-[13px] text-ink-2">
            {type === "BUY" ? "Total cost, incl. fee" : "Est. proceeds, after fee"}
          </span>
          <span className="tnum font-mono text-xl font-semibold text-ink">
            {total == null ? "—" : fmtRp(total)}
          </span>
        </div>

        {error && <ErrorNote message={error} />}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} busy={busy}>
            Save changes
          </Button>
        </div>
      </div>
    </Modal>
  );
}
