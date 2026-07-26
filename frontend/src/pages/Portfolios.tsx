import { Briefcase, Plus } from "@phosphor-icons/react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api, type Holdings, type Performance, type Portfolio } from "../api/client";
import { useAsync } from "../lib/hooks";
import { DASH, fmtDate, fmtPct, fmtRp, fmtSignedRp, signClass } from "../lib/format";
import {
  Button,
  EmptyState,
  ErrorNote,
  Field,
  Modal,
  Panel,
  Skeleton,
} from "../components/ui";

/** One portfolio plus the data that makes its card worth looking at. */
interface Enriched {
  portfolio: Portfolio;
  holdings: Holdings | null;
  perf: Performance | null;
}

/** Load every portfolio, then its holdings + a 6-month curve in parallel so
 *  each card can show real value, P&L, and a trend — not just a name. */
async function loadPortfolios(): Promise<Enriched[]> {
  const portfolios = await api.listPortfolios();
  return Promise.all(
    portfolios.map(async (portfolio) => {
      const [holdings, perf] = await Promise.all([
        api.holdings(portfolio.id).catch(() => null),
        api.performance(portfolio.id, "6mo").catch(() => null),
      ]);
      return { portfolio, holdings, perf };
    }),
  );
}

export function PortfoliosPage() {
  const { data, loading, error, reload } = useAsync(loadPortfolios, []);
  const [creating, setCreating] = useState(false);

  const rows = data ?? [];
  const hasAny = rows.length > 0;

  // Aggregate net worth = priced holdings + tracked cash, across everything.
  let netWorth = 0;
  let totalCost = 0;
  let totalPnl = 0;
  let pnlKnown = false;
  let holdingCount = 0;
  for (const { holdings } of rows) {
    const t = holdings?.totals;
    if (!t) continue;
    if (t.market_value != null) netWorth += t.market_value;
    if (t.cash_tracked) netWorth += t.cash_balance;
    if (t.unrealized_pnl != null) {
      totalPnl += t.unrealized_pnl;
      totalCost += t.cost_basis;
      pnlKnown = true;
    }
    holdingCount += holdings?.holdings.length ?? 0;
  }
  const totalPnlPct = pnlKnown && totalCost > 0 ? (totalPnl / totalCost) * 100 : null;

  return (
    <div className="mx-auto w-full max-w-[1200px] px-4 pb-16 pt-6">
      {/* header: net worth is the headline; the button is the only other move */}
      <div
        className="rise mb-8 flex flex-wrap items-end justify-between gap-6 border-b border-line pb-6"
        style={{ "--rise": 0 } as React.CSSProperties}
      >
        <div>
          <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-ink-3">
            {hasAny ? "Net worth" : "Portfolios"}
          </p>
          {loading ? (
            <Skeleton className="mt-3 h-11 w-64" />
          ) : hasAny ? (
            <>
              <p className="tnum mt-2 font-mono text-4xl font-semibold leading-none tracking-tight text-ink sm:text-5xl">
                {fmtRp(netWorth)}
              </p>
              <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px]">
                <span className={`tnum font-mono font-medium ${signClass(totalPnl)}`}>
                  {fmtSignedRp(totalPnl)}
                </span>
                <span className="text-ink-3">
                  unrealized
                  {totalPnlPct != null ? ` · ${fmtPct(totalPnlPct, true)} of cost` : ""}
                </span>
                <span className="text-ink-3/50">·</span>
                <span className="tnum text-ink-3">
                  {rows.length} portfolio{rows.length > 1 ? "s" : ""} · {holdingCount}{" "}
                  holding{holdingCount === 1 ? "" : "s"}
                </span>
              </p>
            </>
          ) : (
            <h1 className="mt-2 font-serif text-4xl font-semibold text-ink">
              Portfolios
            </h1>
          )}
        </div>
        {(hasAny || loading) && (
          <Button onClick={() => setCreating(true)}>
            <Plus size={15} weight="bold" /> New portfolio
          </Button>
        )}
      </div>

      {error && <ErrorNote message={error} />}

      {loading ? (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Panel key={i} className="overflow-hidden">
              <div className="p-5">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="mt-4 h-7 w-40" />
                <Skeleton className="mt-3 h-3 w-28" />
              </div>
              <Skeleton className="h-14 w-full rounded-none" />
            </Panel>
          ))}
        </div>
      ) : !hasAny ? (
        <Panel>
          <EmptyState
            icon={<Briefcase size={30} weight="light" />}
            title="No portfolios yet"
            body="Create your first portfolio, then record buys and sells to track value, performance against the IHSG, and risk."
            action={
              <Button onClick={() => setCreating(true)}>
                <Plus size={15} weight="bold" /> New portfolio
              </Button>
            }
          />
        </Panel>
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((row, i) => (
            <PortfolioCard key={row.portfolio.id} row={row} index={i} />
          ))}
        </div>
      )}

      {creating && (
        <CreatePortfolioModal
          onClose={() => setCreating(false)}
          onSaved={reload}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Card — value, P&L, holdings count, and a 6-month sparkline           */
/* ------------------------------------------------------------------ */

function PortfolioCard({ row, index }: { row: Enriched; index: number }) {
  const { portfolio: p, holdings, perf } = row;
  const t = holdings?.totals;
  const marketValue = t?.market_value ?? null;
  const pnl = t?.unrealized_pnl ?? null;
  const pnlPct =
    pnl != null && t && t.cost_basis > 0 ? (pnl / t.cost_basis) * 100 : null;
  const count = holdings?.holdings.length ?? 0;

  const curve = perf?.points.map((pt) => pt.portfolio_value) ?? [];
  const up = curve.length >= 2 ? curve[curve.length - 1] >= curve[0] : (pnl ?? 0) >= 0;

  return (
    <Link
      to={`/portfolios/${p.id}`}
      className="rise group block"
      style={{ "--rise": index + 1 } as React.CSSProperties}
    >
      <Panel className="h-full overflow-hidden transition-all duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:-translate-y-1 group-hover:ring-accent/35 group-hover:shadow-[0_1px_2px_rgb(23_30_54/0.06),0_26px_52px_-30px_rgb(43_53_112/0.4)]">
        <div className="p-5">
          <div className="flex items-start justify-between gap-3">
            <p className="font-serif text-lg font-semibold leading-snug text-ink transition-colors group-hover:text-accent">
              {p.name}
            </p>
            <span className="tnum mt-0.5 shrink-0 rounded-full bg-ink/[0.05] px-2 py-0.5 font-mono text-[11px] text-ink-3">
              {count} {count === 1 ? "holding" : "holdings"}
            </span>
          </div>
          {p.description && (
            <p className="mt-1 line-clamp-1 text-[13px] text-ink-3">
              {p.description}
            </p>
          )}

          <p className="tnum mt-4 font-mono text-[26px] font-semibold leading-none text-ink">
            {marketValue == null ? DASH : fmtRp(marketValue)}
          </p>
          <div className="mt-2 flex items-center gap-2 text-[13px]">
            {pnl == null ? (
              <span className="text-ink-3">No priced holdings yet</span>
            ) : (
              <>
                <span className={`tnum font-mono font-medium ${signClass(pnl)}`}>
                  {fmtSignedRp(pnl)}
                </span>
                {pnlPct != null && (
                  <span className={`tnum font-mono text-xs ${signClass(pnl)}`}>
                    {fmtPct(pnlPct, true)}
                  </span>
                )}
              </>
            )}
            <span className="tnum ml-auto text-xs text-ink-3">
              since {fmtDate(p.created_at)}
            </span>
          </div>
        </div>

        {/* nested inset footer — the card's one visual, kept honest with data */}
        <div className="flex items-center gap-3 border-t border-line bg-panel-2/40 px-5 py-3">
          {curve.length >= 2 ? (
            <>
              <span className="shrink-0 font-mono text-[11px] text-ink-3">6-mo</span>
              <div className="min-w-0 flex-1">
                <Sparkline values={curve} up={up} />
              </div>
            </>
          ) : (
            <p className="text-[11px] text-ink-3">
              Record a transaction to see performance
            </p>
          )}
        </div>
      </Panel>
    </Link>
  );
}

/** Tiny inline area sparkline. Green when the period ends up, red when down;
 *  stroke width stays crisp under the non-uniform scale. */
function Sparkline({ values, up }: { values: number[]; up: boolean }) {
  const w = 120;
  const h = 30;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - 3 - ((v - min) / range) * (h - 6);
    return [x, y] as const;
  });
  const line = pts
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`)
    .join(" ");
  const area = `${line} L ${w} ${h} L 0 ${h} Z`;
  const color = up ? "var(--color-pos)" : "var(--color-neg)";

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className="h-8 w-full"
      aria-hidden
    >
      <path d={area} fill={color} fillOpacity="0.09" />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

/* ------------------------------------------------------------------ */

function CreatePortfolioModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!name.trim()) return setError("Give the portfolio a name.");
    setBusy(true);
    setError(null);
    try {
      await api.createPortfolio(name.trim(), description.trim() || undefined);
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="New portfolio" onClose={onClose}>
      <div className="flex flex-col gap-4">
        <Field
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Long-term IDX"
          autoFocus
        />
        <Field
          label="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Blue chips, quarterly rebalance"
        />
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} busy={busy}>
            Create
          </Button>
        </div>
      </div>
    </Modal>
  );
}
