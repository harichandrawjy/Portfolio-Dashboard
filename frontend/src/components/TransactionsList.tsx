import { PencilSimple, Trash } from "@phosphor-icons/react";
import { useState } from "react";

import { api, type Transaction, type TransactionList } from "../api/client";
import { fmtDate, fmtNum, fmtRp } from "../lib/format";
import { EditTransactionModal } from "./EditTransactionModal";
import {
  Button,
  ConfirmDialog,
  ErrorNote,
  Panel,
  PanelHeader,
  Skeleton,
  useToast,
} from "./ui";

export function TransactionsList({
  portfolioId,
  transactions,
  loading,
  error,
  onChanged,
  onShowMore,
  atLimit = false,
  step = 25,
}: {
  portfolioId: string;
  transactions: TransactionList | null;
  loading: boolean;
  error?: string | null;
  onChanged: () => void;
  onShowMore?: () => void;
  /** the API's page ceiling has been reached */
  atLimit?: boolean;
  step?: number;
}) {
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [confirming, setConfirming] = useState<Transaction | null>(null);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const toast = useToast();

  // Hide the panel only when the ledger is genuinely empty — never when the
  // request failed, which is what the error branch below is for.
  if (!error && !loading && (transactions?.items.length ?? 0) === 0) return null;

  const remove = async () => {
    if (!confirming) return;
    setDeleteError(null);
    setDeleting(true);
    try {
      await api.deleteTransaction(portfolioId, confirming.id);
      toast(
        `Deleted the ${confirming.type === "BUY" ? "buy" : "sell"} of ${confirming.ticker}. Holdings and cash updated.`,
      );
      setConfirming(null);
      onChanged();
    } catch (e) {
      setDeleteError((e as Error).message);
    } finally {
      setDeleting(false);
    }
  };

  const shown = transactions?.items.length ?? 0;
  const total = transactions?.total ?? 0;
  const remaining = Math.max(0, total - shown);
  // Only the first load gets skeletons; growing the page keeps the rows on
  // screen and puts the pending state on the button instead.
  const initialLoading = loading && transactions === null;

  return (
    <Panel tone="flat">
      <PanelHeader
        seq="05"
        title="Transactions" meta={
          transactions
            ? shown < total
              ? `${fmtNum(shown)} of ${fmtNum(total)}`
              : fmtNum(total)
            : undefined
        }
      />
      <div className="px-5 pb-4">
        {error ? (
          <ErrorNote message={error} />
        ) : initialLoading ? (
          <div className="space-y-2">
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : (
          <ul className="divide-y divide-line">
            {transactions!.items.map((t) => (
              <li
                key={t.id}
                className="flex items-center gap-3 py-2.5 text-[13px] transition-colors hover:bg-ink/[0.02]"
              >
                {/* Category, not sign: weight separates a buy from a sell so
                    green and red stay reserved for signed values. */}
                <span
                  className={`inline-flex w-[42px] shrink-0 justify-center py-0.5 text-[11px] font-semibold ${
                    t.type === "BUY"
                      ? "bg-ink text-panel"
                      : "bg-panel text-ink-2 ring-1 ring-line-2"
                  }`}
                >
                  {t.type === "BUY" ? "Buy" : "Sell"}
                </span>
                <div className="flex min-w-0 items-baseline gap-2">
                  <span className="text-[13px] font-semibold text-ink">
                    {t.ticker}
                  </span>
                  <span className="tnum truncate text-ink-3">
                    {fmtNum(t.lots)} lot{t.lots > 1 ? "s" : ""} ·{" "}
                    {fmtRp(t.price_per_share)}
                  </span>
                </div>
                <span className="tnum ml-auto shrink-0 text-ink">
                  {fmtRp(t.shares * t.price_per_share)}
                </span>
                <span className="tnum hidden w-[92px] shrink-0 text-right text-xs text-ink-3 sm:block">
                  {fmtDate(t.executed_at)}
                </span>
                <div className="flex shrink-0 items-center">
                  <button
                    onClick={() => setEditing(t)}
                    className="p-2 text-ink-3 sm:p-1.5 outline-none press hover:bg-panel-2 hover:text-ink active:bg-panel-2 focus-visible:ring-2 focus-visible:ring-accent" aria-label={`Edit ${t.type} ${t.ticker}`}
                  >
                    <PencilSimple size={14} weight="light" />
                  </button>
                  <button
                    onClick={() => {
                      setDeleteError(null);
                      setConfirming(t);
                    }}
                    className="p-2 text-ink-3 sm:p-1.5 outline-none press hover:bg-neg hover:text-white active:bg-neg active:text-white focus-visible:ring-2 focus-visible:ring-accent" aria-label={`Delete ${t.type} ${t.ticker}`}
                  >
                    <Trash size={14} weight="light" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {!error && !initialLoading && remaining > 0 && (
          <div className="mt-3 flex justify-center">
            {atLimit || !onShowMore ? (
              <p className="text-xs text-ink-3">
                Showing the {fmtNum(shown)} most recent · {fmtNum(remaining)}{" "}
                older not listed
              </p>
            ) : (
              <Button variant="ghost" onClick={onShowMore} busy={loading}>
                Show {fmtNum(Math.min(step, remaining))} more
              </Button>
            )}
          </div>
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

      {confirming && (
        <ConfirmDialog
          title="Delete transaction" danger
          confirmLabel="Delete transaction" busy={deleting}
          error={deleteError}
          onClose={() => setConfirming(null)}
          onConfirm={remove}
          body={
            <>
              Delete the{" "}
              <span className="font-semibold text-ink">
                {confirming.type === "BUY" ? "buy" : "sell"} of{" "}
                {fmtNum(confirming.lots)} lot
                {confirming.lots > 1 ? "s" : ""} of {confirming.ticker}
              </span>{" "}
              on {fmtDate(confirming.executed_at)}? Holdings and cash are
              derived from this ledger, so both will change.
            </>
          }
        />
      )}
    </Panel>
  );
}
