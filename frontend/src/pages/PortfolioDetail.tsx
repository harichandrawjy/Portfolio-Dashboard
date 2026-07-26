import { ArrowLeft, Trash } from "@phosphor-icons/react";
import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, type RangeKey, type TxnType } from "../api/client";
import { AddTransactionModal } from "../components/AddTransactionModal";
import { CashModal } from "../components/CashModal";
import { AllocationDonut } from "../components/AllocationDonut";
import { HoldingsTable } from "../components/HoldingsTable";
import { PerformanceChart } from "../components/PerformanceChart";
import { SummaryCards } from "../components/SummaryCards";
import { TransactionsList } from "../components/TransactionsList";
import { Button, ConfirmDialog, ErrorNote } from "../components/ui";
import { useAsync } from "../lib/hooks";

export function PortfolioDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [range, setRange] = useState<RangeKey>("1y");
  // null = closed; {} = blank add; {ticker,type} = pre-set from a holding row
  const [trade, setTrade] = useState<
    { ticker?: string; type?: TxnType } | null
  >(null);
  const [cashOpen, setCashOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const refresh = useCallback(() => setRefreshTick((t) => t + 1), []);

  const removePortfolio = async () => {
    setDeleteError(null);
    setDeleting(true);
    try {
      await api.deletePortfolio(id);
      navigate("/", { replace: true });
    } catch (e) {
      setDeleteError((e as Error).message);
      setDeleting(false);
    }
  };

  const portfolio = useAsync(() => api.getPortfolio(id), [id]);
  const holdings = useAsync(() => api.holdings(id), [id, refreshTick]);
  const allocation = useAsync(() => api.allocation(id), [id, refreshTick]);
  const performance = useAsync(
    () => api.performance(id, range),
    [id, range, refreshTick],
  );
  const metrics = useAsync(() => api.metrics(id, range), [id, range, refreshTick]);
  const transactions = useAsync(
    () => api.transactions(id, 15),
    [id, refreshTick],
  );

  if (portfolio.error) {
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-8">
        <ErrorNote message={portfolio.error} />
      </div>
    );
  }

  const rise = (i: number) =>
    ({ "--rise": i }) as React.CSSProperties;

  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-5 px-4 pb-12 pt-4">
      <div className="rise flex flex-wrap items-center gap-3" style={rise(0)}>
        <Link
          to="/"
          className="flex items-center gap-1.5 text-[13px] text-ink-3 transition-colors hover:text-ink-2"
        >
          <ArrowLeft size={14} weight="light" /> Portfolios
        </Link>
        <span className="text-ink-3/60">/</span>
        <h1 className="font-serif text-2xl font-semibold text-ink">
          {portfolio.data?.name ?? "…"}
        </h1>
        {portfolio.data?.description && (
          <span className="hidden text-[13px] text-ink-3 sm:inline">
            {portfolio.data.description}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => {
              setDeleteError(null);
              setConfirmDelete(true);
            }}
            className="rounded-[6px] p-2 text-ink-3 outline-none transition-colors hover:bg-neg/10 hover:text-neg focus-visible:ring-2 focus-visible:ring-accent/70"
            aria-label="Delete portfolio"
            title="Delete portfolio"
          >
            <Trash size={16} weight="light" />
          </button>
          <Button variant="ghost" onClick={() => setCashOpen(true)}>
            Cash
          </Button>
          <Button onClick={() => setTrade({})}>Add transaction</Button>
        </div>
      </div>

      <div className="rise" style={rise(1)}>
        <SummaryCards
          holdings={holdings.data}
          metrics={metrics.data}
          loading={holdings.loading || metrics.loading}
        />
      </div>

      {/* overview: the portfolio's trend and its sector breakdown, side by
          side — both handle a flexible column, so nothing overflows */}
      <div
        className="rise grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]"
        style={rise(2)}
      >
        <PerformanceChart
          performance={performance.data}
          loading={performance.loading}
          range={range}
          onRangeChange={setRange}
        />
        <AllocationDonut
          allocation={allocation.data}
          loading={allocation.loading}
        />
      </div>

      {/* the wide holdings table gets the full width so every column and the
          Buy/Sell actions stay visible without horizontal scrolling */}
      <div className="rise" style={rise(3)}>
        <HoldingsTable
          holdings={holdings.data}
          loading={holdings.loading}
          onAddTransaction={() => setTrade({})}
          onTrade={(ticker, type) => setTrade({ ticker, type })}
        />
      </div>

      <div className="rise" style={rise(4)}>
        <TransactionsList
          portfolioId={id}
          transactions={transactions.data}
          loading={transactions.loading}
          onChanged={refresh}
        />
      </div>

      {trade && (
        <AddTransactionModal
          portfolioId={id}
          initialTicker={trade.ticker}
          initialType={trade.type}
          onClose={() => setTrade(null)}
          onSaved={refresh}
        />
      )}
      {cashOpen && (
        <CashModal
          portfolioId={id}
          onClose={() => setCashOpen(false)}
          onChanged={refresh}
        />
      )}
      {confirmDelete && (
        <ConfirmDialog
          title="Delete portfolio"
          danger
          confirmLabel="Delete portfolio"
          busy={deleting}
          error={deleteError}
          onClose={() => setConfirmDelete(false)}
          onConfirm={removePortfolio}
          body={
            <>
              Permanently delete{" "}
              <span className="font-semibold text-ink">
                {portfolio.data?.name ?? "this portfolio"}
              </span>
              {transactions.data && transactions.data.total > 0 && (
                <>
                  {" "}
                  and its{" "}
                  <span className="font-semibold text-ink">
                    {transactions.data.total} transaction
                    {transactions.data.total > 1 ? "s" : ""}
                  </span>
                </>
              )}
              ? This can't be undone.
            </>
          }
        />
      )}
    </div>
  );
}
