import { Plus } from "@phosphor-icons/react";
import { useState, type FormEvent } from "react";
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
  SectionHead,
  Skeleton,
} from "../components/ui";

/** One portfolio plus the data that makes its card worth looking at. */
interface Enriched {
  portfolio: Portfolio;
  holdings: Holdings | null;
  perf: Performance | null;
  /** the holdings call rejected — distinct from "holds nothing priced" */
  holdingsFailed: boolean;
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
      return { portfolio, holdings, perf, holdingsFailed: holdings === null };
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
  const anyFailed = rows.some((r) => r.holdingsFailed);

  return (
    <div className="mx-auto w-full max-w-[1200px] px-4 pb-24 pt-8">
      {/* ── 01 — the aggregate, set as the page's poster figure ───────── */}
      <div className="rise" style={{ "--rise": 0 } as React.CSSProperties}>
        <SectionHead
          seq="01" title={hasAny || loading ? "Net worth" : "Portfolios"}
          right={
            (hasAny || loading) && (
              <Button onClick={() => setCreating(true)}>
                <Plus size={13} weight="bold" /> New portfolio
              </Button>
            )
          }
        />

        {loading ? (
          <Skeleton className="mt-6 h-[92px] w-full max-w-xl" />
        ) : hasAny ? (
          <div className="mt-6 grid gap-x-10 gap-y-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:items-end">
            <div>
              <h1 className="sr-only">Portfolios</h1>
              {/* the figure is the headline — condensed, heaviest cut, set
                  flush so it reads as a printed mark rather than a heading */}
              <p className="tnum w-condensed break-words text-[clamp(3rem,8.5vw,5.75rem)] font-extrabold leading-[0.86] tracking-[-0.035em] text-ink">
                {fmtRp(netWorth)}
              </p>
            </div>

            {/* The supporting figures, ruled off as a definition row. Flex
                rather than fixed tracks so a row that doesn't divide evenly
                never leaves an unpainted track showing the hairline bed. */}
            <dl className="flex flex-wrap gap-px border-t border-line bg-line lg:border-t-0">
              <Figure
                label="Unrealized" value={fmtSignedRp(totalPnl)}
                tone={signClass(totalPnl)}
                note={totalPnlPct != null ? `${fmtPct(totalPnlPct, true)} of cost` : undefined}
              />
              <Figure
                label="Portfolios" value={String(rows.length)}
                note={anyFailed ? "some didn't load" : "tracked"}
                warn={anyFailed}
              />
              <Figure
                label="Holdings" value={String(holdingCount)}
                note="open positions"
              />
            </dl>
          </div>
        ) : null}
      </div>

      {error && (
        <Panel className="mt-10">
          {/* without this branch the failure renders "No portfolios yet" underneath the error — telling you that you have none */}
          <EmptyState
            title="Couldn't load your portfolios" body={error}
            action={
              <Button variant="ghost" onClick={reload}>
                Try again
              </Button>
            }
          />
        </Panel>
      )}

      {/* ── 02 — the register ────────────────────────────────────────── */}
      {error ? null : (
        <div
          className="rise mt-12" style={{ "--rise": 1 } as React.CSSProperties}
        >
          {(hasAny || loading) && <SectionHead seq="02" title="The register" />}

          {loading ? (
            <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="border-t-[3px] border-line-2 pt-4">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="mt-5 h-8 w-40" />
                  <Skeleton className="mt-3 h-3 w-24" />
                  <Skeleton className="mt-5 h-10 w-full" />
                </div>
              ))}
            </div>
          ) : !hasAny ? (
            <Panel>
              <EmptyState
                title="No portfolios yet" body="Create your first portfolio, then record buys and sells to track value, performance against the IHSG, and risk." action={
                  <Button onClick={() => setCreating(true)}>
                    <Plus size={13} weight="bold" /> New portfolio
                  </Button>
                }
              />
            </Panel>
          ) : (
            <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {rows.map((row, i) => (
                <PortfolioCard key={row.portfolio.id} row={row} index={i} />
              ))}
            </div>
          )}
        </div>
      )}

      {creating && (
        <CreatePortfolioModal onClose={() => setCreating(false)} onSaved={reload} />
      )}
    </div>
  );
}

/** One cell of the aggregate definition row. */
function Figure({
  label,
  value,
  note,
  tone = "text-ink",
  warn = false,
}: {
  label: string;
  value: string;
  note?: string;
  tone?: string;
  warn?: boolean;
}) {
  return (
    <div className="flex-1 basis-[150px] bg-bg px-3 py-3 first:pl-0">
      <dt className="w-wide text-[10px] font-bold uppercase tracking-[0.14em] text-ink-3">
        {label}
      </dt>
      <dd className={`tnum mt-2 text-[19px] font-bold leading-none ${tone}`}>
        {value}
      </dd>
      {note && (
        <dd
          className={`tnum mt-1.5 text-[11px] leading-tight ${warn ? "text-warn" : "text-ink-3"}`}
        >
          {note}
        </dd>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Card — a ruled block: value, P&L, holdings count, 6-month columns    */
/* ------------------------------------------------------------------ */

function PortfolioCard({ row, index }: { row: Enriched; index: number }) {
  const { portfolio: p, holdings, perf, holdingsFailed } = row;
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
      className="rise group block outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg" style={{ "--rise": index + 2 } as React.CSSProperties}
    >
      <article className="flex h-full flex-col border-t-[3px] border-line-2 pt-4 transition-colors group-hover:border-accent">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="w-wide text-[12px] font-bold uppercase leading-tight tracking-[0.12em] text-ink transition-colors group-hover:text-accent">
            {p.name}
          </h3>
          <span className="tnum shrink-0 text-[11px] font-medium text-ink-3">
            {count} {count === 1 ? "holding" : "holdings"}
          </span>
        </div>

        {p.description && (
          <p className="mt-1.5 line-clamp-1 text-[12px] text-ink-3">
            {p.description}
          </p>
        )}

        <p className="tnum w-condensed mt-5 text-[30px] font-extrabold leading-none tracking-[-0.02em] text-ink">
          {marketValue == null ? DASH : fmtRp(marketValue)}
        </p>

        <div className="mt-2.5 flex items-baseline gap-2 text-[12px]">
          {holdingsFailed ? (
            <span className="font-medium text-warn">Couldn't load this portfolio</span>
          ) : pnl == null ? (
            <span className="text-ink-3">No priced holdings yet</span>
          ) : (
            <>
              <span className={`tnum font-bold ${signClass(pnl)}`}>
                {fmtSignedRp(pnl)}
              </span>
              {pnlPct != null && (
                <span className={`tnum font-medium ${signClass(pnl)}`}>
                  {fmtPct(pnlPct, true)}
                </span>
              )}
            </>
          )}
        </div>

        {/* the card's one visual: the 6-month curve as columns, which reads
            as measured data rather than as decoration */}
        <div className="mt-auto flex items-end gap-3 pt-5">
          {curve.length >= 2 ? (
            <>
              <span className="w-wide shrink-0 text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
                6&nbsp;mo
              </span>
              <div className="min-w-0 flex-1">
                <Columns values={curve} up={up} />
              </div>
            </>
          ) : (
            <p className="text-[11px] text-ink-3">
              Record a transaction to see performance
            </p>
          )}
          <span className="tnum shrink-0 text-[10px] text-ink-3">
            since {fmtDate(p.created_at)}
          </span>
        </div>
      </article>
    </Link>
  );
}

/**
 * The 6-month curve drawn as a column chart. Columns rather than a smooth
 * area: this system states data in discrete measured marks, and a hard-edged
 * bar survives being 30px tall where a 1.5px spline turns to mush.
 * Sampled down to a fixed column count so every card reads at one rhythm
 * regardless of how many points its range returned.
 */
function Columns({ values, up }: { values: number[]; up: boolean }) {
  const COLS = 34;
  const step = Math.max(1, Math.floor(values.length / COLS));
  const sampled: number[] = [];
  for (let i = 0; i < values.length && sampled.length < COLS; i += step) {
    sampled.push(values[i]);
  }
  const min = Math.min(...sampled);
  const max = Math.max(...sampled);
  const range = max - min || 1;
  const color = up ? "var(--color-pos)" : "var(--color-neg)";

  return (
    <div className="flex h-9 items-end gap-px" aria-hidden>
      {sampled.map((v, i) => (
        <span
          key={i}
          className="min-w-0 flex-1" style={{
            // a floor so a flat stretch still reads as a row of marks
            height: `${8 + ((v - min) / range) * 92}%`,
            backgroundColor: color,
            // the run reads as one shape, with the newest columns strongest
            opacity: 0.35 + (i / (sampled.length - 1 || 1)) * 0.65,
          }}
        />
      ))}
    </div>
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

  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
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
      {/* a real form, so Enter in either field creates the portfolio */}
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field
          label="Name" value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Long-term IDX" autoFocus
        />
        <Field
          label="Description (optional)" value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Blue chips, quarterly rebalance"
        />
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" busy={busy}>
            Create
          </Button>
        </div>
      </form>
    </Modal>
  );
}
