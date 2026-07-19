import { ArrowLeft } from "@phosphor-icons/react";
import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, type RangeKey } from "../api/client";
import { AddTransactionModal } from "../components/AddTransactionModal";
import { AllocationDonut } from "../components/AllocationDonut";
import { HoldingsTable } from "../components/HoldingsTable";
import { PerformanceChart } from "../components/PerformanceChart";
import { SummaryCards } from "../components/SummaryCards";
import { TransactionsList } from "../components/TransactionsList";
import { Button, ErrorNote } from "../components/ui";
import { useAsync } from "../lib/hooks";

export function PortfolioDetailPage() {
  const { id = "" } = useParams();
  const [range, setRange] = useState<RangeKey>("1y");
  const [adding, setAdding] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);
  const refresh = useCallback(() => setRefreshTick((t) => t + 1), []);

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
        <h1 className="text-xl font-semibold tracking-tight text-ink">
          {portfolio.data?.name ?? "…"}
        </h1>
        {portfolio.data?.description && (
          <span className="hidden text-[13px] text-ink-3 sm:inline">
            {portfolio.data.description}
          </span>
        )}
        <div className="ml-auto">
          <Button onClick={() => setAdding(true)}>Add transaction</Button>
        </div>
      </div>

      <div className="rise" style={rise(1)}>
        <SummaryCards
          holdings={holdings.data}
          metrics={metrics.data}
          loading={holdings.loading || metrics.loading}
        />
      </div>

      <div className="rise" style={rise(2)}>
        <PerformanceChart
          performance={performance.data}
          loading={performance.loading}
          range={range}
          onRangeChange={setRange}
        />
      </div>

      <div
        className="rise grid grid-cols-1 gap-5 lg:grid-cols-[2fr_1fr]"
        style={rise(3)}
      >
        <HoldingsTable
          holdings={holdings.data}
          loading={holdings.loading}
          onAddTransaction={() => setAdding(true)}
        />
        <AllocationDonut
          allocation={allocation.data}
          loading={allocation.loading}
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

      {adding && (
        <AddTransactionModal
          portfolioId={id}
          onClose={() => setAdding(false)}
          onSaved={refresh}
        />
      )}
    </div>
  );
}
