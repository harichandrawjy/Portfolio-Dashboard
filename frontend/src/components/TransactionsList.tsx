import { PencilSimple, Trash } from "@phosphor-icons/react";
import { useState } from "react";

import { api, type Transaction, type TransactionList } from "../api/client";
import { fmtDate, fmtNum, fmtRp } from "../lib/format";
import { EditTransactionModal } from "./EditTransactionModal";
import { ErrorNote, Panel, PanelHeader, Skeleton } from "./ui";

export function TransactionsList({
  portfolioId,
  transactions,
  loading,
  onChanged,
}: {
  portfolioId: string;
  transactions: TransactionList | null;
  loading: boolean;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [editing, setEditing] = useState<Transaction | null>(null);

  if (!loading && (transactions?.items.length ?? 0) === 0) return null;

  const remove = async (id: string) => {
    setError(null);
    setDeleting(id);
    try {
      await api.deleteTransaction(portfolioId, id);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <Panel tone="flat">
      <PanelHeader
        title="Transactions"
        meta={transactions ? String(transactions.total) : undefined}
      />
      <div className="px-5 pb-4">
        {error && (
          <div className="mb-3">
            <ErrorNote message={error} />
          </div>
        )}
        {loading ? (
          <div className="space-y-2">
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : (
          <ul className="divide-y divide-line/50">
            {transactions!.items.map((t) => (
              <li
                key={t.id}
                className="flex items-center gap-3 py-2.5 text-[13px] transition-colors hover:bg-ink/[0.02]"
              >
                <span
                  className={`inline-flex w-[42px] shrink-0 justify-center rounded-full py-0.5 text-[11px] font-semibold ring-1 ${
                    t.type === "BUY"
                      ? "bg-pos/10 text-pos ring-pos/25"
                      : "bg-neg/10 text-neg ring-neg/25"
                  }`}
                >
                  {t.type === "BUY" ? "Buy" : "Sell"}
                </span>
                <div className="flex min-w-0 items-baseline gap-2">
                  <span className="font-mono text-sm font-semibold text-ink">
                    {t.ticker}
                  </span>
                  <span className="tnum truncate text-ink-3">
                    {fmtNum(t.lots)} lot{t.lots > 1 ? "s" : ""} ·{" "}
                    {fmtRp(t.price_per_share)}
                  </span>
                </div>
                <span className="tnum ml-auto shrink-0 font-mono text-ink">
                  {fmtRp(t.shares * t.price_per_share)}
                </span>
                <span className="tnum hidden w-[92px] shrink-0 text-right text-xs text-ink-3 sm:block">
                  {fmtDate(t.executed_at)}
                </span>
                <div className="flex shrink-0 items-center">
                  <button
                    onClick={() => setEditing(t)}
                    className="rounded-[7px] p-1.5 text-ink-3 transition-colors hover:bg-ink/5 hover:text-ink"
                    aria-label={`Edit ${t.type} ${t.ticker}`}
                  >
                    <PencilSimple size={14} weight="light" />
                  </button>
                  <button
                    onClick={() => remove(t.id)}
                    disabled={deleting === t.id}
                    className="rounded-[7px] p-1.5 text-ink-3 transition-colors hover:bg-neg/10 hover:text-neg disabled:opacity-40"
                    aria-label={`Delete ${t.type} ${t.ticker}`}
                  >
                    <Trash size={14} weight="light" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {editing && (
        <EditTransactionModal
          portfolioId={portfolioId}
          transaction={editing}
          onClose={() => setEditing(null)}
          onSaved={onChanged}
        />
      )}
    </Panel>
  );
}
