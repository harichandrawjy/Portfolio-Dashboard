import { ArrowLeft, PencilSimple, Trash } from "@phosphor-icons/react";
import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, type RangeKey, type TxnType } from "../api/client";
import { AddTransactionModal } from "../components/AddTransactionModal";
import { CashModal } from "../components/CashModal";
import { EditPortfolioModal } from "../components/EditPortfolioModal";
import { AllocationDonut } from "../components/AllocationDonut";
import { FrontierChart } from "../components/FrontierChart";
import { HoldingsTable } from "../components/HoldingsTable";
import { PortfolioFirstRun } from "../components/PortfolioFirstRun";
import { PerformanceChart } from "../components/PerformanceChart";
import { SummaryCards } from "../components/SummaryCards";
import { TransactionsList } from "../components/TransactionsList";
import { Button, ConfirmDialog, ErrorNote, useToast } from "../components/ui";
import { useAsync } from "../lib/hooks";

/** Ledger page sizes. TXN_MAX mirrors the API's `limit` ceiling. */
const TXN_PAGE = 15;
const TXN_STEP = 25;
const TXN_MAX = 200;

export function PortfolioDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [range, setRange] = useState<RangeKey>("1y");
  // null = closed; {} = blank add; {ticker,type} = pre-set from a holding row
  const [trade, setTrade] = useState<
    { ticker?: string; type?: TxnType } | null
  >(null);
  const [cashOpen, setCashOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const toast = useToast();
  const [refreshTick, setRefreshTick] = useState(0);
  const refresh = useCallback(() => setRefreshTick((t) => t + 1), []);

  // The ledger loads a page at a time. Growing the limit rather than
  // accumulating pages keeps the list consistent with edits and deletes: any
  // refresh refetches exactly what is on screen. TXN_MAX is the API's own cap.
  const [txnLimit, setTxnLimit] = useState(TXN_PAGE);
  const showMoreTransactions = useCallback(
    () => setTxnLimit((l) => Math.min(l + TXN_STEP, TXN_MAX)),
    [],
  );

  const removePortfolio = async () => {
    setDeleteError(null);
    setDeleting(true);
    try {
      await api.deletePortfolio(id);
      // the toast lives above the router, so it survives this navigation
      toast(`Deleted "${portfolio.data?.name ?? "the portfolio"}".`);
      navigate("/", { replace: true });
    } catch (e) {
      setDeleteError((e as Error).message);
      setDeleting(false);
    }
  };

  const portfolio = useAsync(() => api.getPortfolio(id), [id]);
  const holdings = useAsync(() => api.holdings(id), [id, refreshTick]);
  const allocation = useAsync(() => api.allocation(id), [id, refreshTick]);
  const frontier = useAsync(() => api.frontier(id), [id, refreshTick]);
  const performance = useAsync(
    () => api.performance(id, range),
    [id, range, refreshTick],
  );
  const metrics = useAsync(() => api.metrics(id, range), [id, range, refreshTick]);
  const transactions = useAsync(
    () => api.transactions(id, txnLimit),
    [id, txnLimit, refreshTick],
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

  // A failed sibling request must never render as an empty state — "no
  // holdings yet" when the request merely failed is a lie about the data.
  // Name what broke, offer one retry, and let each panel show its own error.
  const failed = (
    [
      ["holdings", holdings],
      ["allocation", allocation],
      ["performance", performance],
      ["metrics", metrics],
      ["transactions", transactions],
    ] as const
  ).filter(([, s]) => s.error !== null);

  const retryFailed = () => {
    for (const [, s] of failed) s.reload();
  };

  // A portfolio with no trades has nothing to chart, allocate or total, and
  // its primary action cannot succeed until it holds cash. Require both loads
  // to have genuinely succeeded — a failed request must not be read as "new".
  const funded = holdings.data?.totals.cash_tracked ?? false;
  const firstRun =
    holdings.data !== null &&
    transactions.data !== null &&
    holdings.error === null &&
    transactions.error === null &&
    holdings.data.holdings.length === 0 &&
    transactions.data.total === 0;

  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-10 px-4 pb-16 pt-6">
      <div className="rise" style={rise(0)}>
        <Link
          to="/"
          className="w-wide -my-1 inline-flex items-center gap-1.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-3 outline-none transition-colors hover:text-accent focus-visible:ring-2 focus-visible:ring-accent"
        >
          <ArrowLeft size={12} weight="bold" /> Portfolios
        </Link>

        <div className="mt-3 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
          <div className="min-w-0">
            {/* the portfolio's name is the page's nameplate — condensed,
                heaviest cut, set as a mark rather than as a heading */}
            <h1 className="w-condensed break-words text-[clamp(2rem,4.5vw,2.75rem)] font-extrabold uppercase leading-[0.92] tracking-[-0.02em] text-ink">
              {portfolio.data?.name ?? "…"}
            </h1>
            {portfolio.data?.description && (
              <p className="mt-2 max-w-[54ch] text-[13px] text-ink-3">
                {portfolio.data.description}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setEditing(true)}
              className="press p-2.5 text-ink-3 outline-none hover:bg-ink hover:text-bg active:bg-ink active:text-bg focus-visible:ring-2 focus-visible:ring-accent sm:p-2"
              aria-label="Edit portfolio name and description"
              title="Edit name and description"
              disabled={portfolio.data === null}
            >
              <PencilSimple size={16} weight="bold" />
            </button>
            <button
              onClick={() => {
                setDeleteError(null);
                setConfirmDelete(true);
              }}
              className="press p-2.5 text-ink-3 outline-none hover:bg-neg hover:text-white active:bg-neg active:text-white focus-visible:ring-2 focus-visible:ring-accent sm:p-2"
              aria-label="Delete portfolio"
              title="Delete portfolio"
            >
              <Trash size={16} weight="bold" />
            </button>
            {/* while there is no cash, a buy cannot succeed — the accent goes
                to the action that can */}
            <Button
              variant={firstRun && !funded ? "primary" : "ghost"}
              onClick={() => setCashOpen(true)}
            >
              Cash
            </Button>
            <Button
              variant={firstRun && !funded ? "ghost" : "primary"}
              onClick={() => setTrade({})}
            >
              Add transaction
            </Button>
          </div>
        </div>
        <div className="rule-draw mt-4 h-0.5 w-full bg-ink" />
      </div>

      {failed.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-l-[3px] border-neg bg-neg/[0.07] px-3 py-2 text-[13px] font-medium text-neg">
          <span>
            Couldn't load {failed.map(([name]) => name).join(", ")}. What you
            see below is incomplete.
          </span>
          <button
            onClick={retryFailed}
            className="ml-auto px-2 py-0.5 text-[11px] font-bold uppercase tracking-[0.12em] underline underline-offset-4 outline-none transition-colors hover:bg-neg hover:text-white hover:no-underline focus-visible:ring-2 focus-visible:ring-accent"
          >
            Retry
          </button>
        </div>
      )}

      {firstRun ? (
        <div className="rise" style={rise(1)}>
          <PortfolioFirstRun
            portfolioId={id}
            cashBalance={holdings.data?.totals.cash_balance ?? 0}
            funded={funded}
            onChanged={refresh}
            onAddTransaction={() => setTrade({})}
          />
        </div>
      ) : (
        <>
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
            className="rise grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]" style={rise(2)}
          >
            <PerformanceChart
              performance={performance.data}
              loading={performance.loading}
              error={performance.error}
              range={range}
              onRangeChange={setRange}
            />
            <AllocationDonut
              allocation={allocation.data}
              loading={allocation.loading}
              error={allocation.error}
            />
          </div>

          {/* the wide holdings table gets the full width so every column and
              the Buy/Sell actions stay visible without horizontal scrolling */}
          <div className="rise" style={rise(3)}>
            <HoldingsTable
              holdings={holdings.data}
              loading={holdings.loading}
              error={holdings.error}
              onAddTransaction={() => setTrade({})}
              onTrade={(ticker, type) => setTrade({ ticker, type })}
            />
          </div>

          {/* Below the holdings on purpose: it is an analytical view of what
              those holdings are, so it only makes sense once you have read
              them. Full width because the chart carries a legend and a table. */}
          <div className="rise" style={rise(4)}>
            <FrontierChart
              frontier={frontier.data}
              loading={frontier.loading}
              error={frontier.error}
            />
          </div>

          <div className="rise" style={rise(5)}>
            <TransactionsList
              portfolioId={id}
              transactions={transactions.data}
              loading={transactions.loading}
              error={transactions.error}
              onChanged={refresh}
              onShowMore={showMoreTransactions}
              atLimit={txnLimit >= TXN_MAX}
              step={TXN_STEP}
            />
          </div>
        </>
      )}

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
      {editing && portfolio.data && (
        <EditPortfolioModal
          portfolio={portfolio.data}
          onClose={() => setEditing(false)}
          // reloads the portfolio itself, not the derived panels: renaming
          // changes no holdings, no cash and no performance, so refetching
          // those would be five wasted requests
          onSaved={portfolio.reload}
        />
      )}
      {confirmDelete && (
        <ConfirmDialog
          title="Delete portfolio" danger
          confirmLabel="Delete portfolio" busy={deleting}
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
