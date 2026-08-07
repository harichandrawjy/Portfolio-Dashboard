import { CaretDown, CaretUp, ChartLine } from "@phosphor-icons/react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { Holding, Holdings } from "../api/client";
import {
  DASH,
  fmtAsOf,
  fmtDateShort,
  fmtNum,
  fmtPct,
  fmtRp,
  fmtSignedRp,
  signClass,
} from "../lib/format";
import {
  Button,
  EmptyState,
  ErrorNote,
  Panel,
  PanelHeader,
  Skeleton,
} from "./ui";

type SortKey = "ticker" | "lots" | "avg_cost_per_share" | "cost_basis" | "last_price" | "market_value" | "unrealized_pnl";

/** Tighter cell padding on a phone: every 40px of chrome is a numeric column
 *  pushed off screen. */
const HEAD_CELL =
  "px-3 py-2.5 sm:px-5 text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3";

/** The ticker stays pinned while the figures scroll under it: without it you
 *  read a row of numbers with no idea which holding they belong to. The
 *  background must be opaque or the scrolled columns show through. */
const STICKY = "sticky left-0 border-r border-line bg-panel";

const COLUMNS: { key: SortKey; label: string; align: "left" | "right" }[] = [
  { key: "ticker", label: "Ticker", align: "left" },
  { key: "lots", label: "Lots", align: "right" },
  // Ordered as two pairs and their difference: what a share cost and what the
  // position cost, then what a share is worth and what the position is worth,
  // then the gap between them. Reading left to right walks the arithmetic,
  // which is why Invested sits beside Avg cost rather than beside Value.
  { key: "avg_cost_per_share", label: "Avg cost", align: "right" },
  { key: "cost_basis", label: "Invested", align: "right" },
  { key: "last_price", label: "Last price", align: "right" },
  { key: "market_value", label: "Value", align: "right" },
  { key: "unrealized_pnl", label: "P&L", align: "right" },
];

export function HoldingsTable({
  holdings,
  loading,
  error,
  onAddTransaction,
  onTrade,
}: {
  holdings: Holdings | null;
  loading: boolean;
  error?: string | null;
  onAddTransaction: () => void;
  onTrade: (ticker: string, type: "BUY" | "SELL") => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("market_value");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const rows = useMemo(() => {
    const list = [...(holdings?.holdings ?? [])];
    const dir = sortDir === "asc" ? 1 : -1;
    list.sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (typeof va === "string" && typeof vb === "string")
        return va.localeCompare(vb) * dir;
      // nulls (missing prices) always sink to the bottom
      if (va == null) return 1;
      if (vb == null) return -1;
      return ((va as number) - (vb as number)) * dir;
    });
    return list;
  }, [holdings, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "ticker" ? "asc" : "desc");
    }
  };

  return (
    <Panel>
      <PanelHeader
        seq="03"
        title="Holdings"
        meta={!loading && rows.length > 0 ? String(rows.length) : undefined}
        right={
          !loading && rows.length > 0 ? (
            <Button variant="text" onClick={onAddTransaction} className="!py-1 text-xs">
              Add transaction
            </Button>
          ) : undefined
        }
      />

      {error ? (
        <div className="px-5 pb-5">
          <ErrorNote message={error} />
        </div>
      ) : loading ? (
        <div className="space-y-2 px-5 pb-5">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<ChartLine size={28} weight="light" />}
          title="No holdings yet" body="Record your first buy to see value, P&L, and allocation for this portfolio." action={<Button onClick={onAddTransaction}>Add transaction</Button>}
        />
      ) : (
        // contain:paint keeps the wide table's overflow inside this scroller.
        // Without it the table's extent reaches the document and the whole
        // page scrolls sideways on a phone — overflow-x-auto alone does not
        // stop it here.
        <div className="overflow-x-auto pb-2 [contain:paint]">
          <table className="w-full min-w-[900px] text-[13px]">
            <thead>
              {/* a heavy rule under the heads, the way a ruled table is set */}
              <tr className="border-b-2 border-ink text-left">
                {COLUMNS.map((c) => (
                  <th
                    key={c.key}
                    // the caret and colour shift are visual-only; announce it
                    aria-sort={
                      sortKey === c.key
                        ? sortDir === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                    className={`${HEAD_CELL} ${
                      c.align === "right" ? "text-right" : ""
                    } ${c.key === "ticker" ? `${STICKY} z-20` : ""}`}
                  >
                    {/* the label is 16px tall; the negative margin grows the
                        hit area past the 24px minimum without moving it */}
                    <button
                      onClick={() => toggleSort(c.key)}
                      className={`-mx-1.5 -my-1.5 inline-flex items-center gap-1 px-1.5 py-1.5 outline-none transition-colors hover:text-ink focus-visible:ring-2 focus-visible:ring-accent ${
                        c.align === "right" ? "flex-row-reverse" : ""
                      } ${sortKey === c.key ? "text-accent" : ""}`}
                    >
                      {c.label}
                      {sortKey === c.key &&
                        (sortDir === "asc" ? (
                          <CaretUp size={10} weight="bold" />
                        ) : (
                          <CaretDown size={10} weight="bold" />
                        ))}
                    </button>
                  </th>
                ))}
                <th className={`${HEAD_CELL} text-left`}>Weight</th>
                <th className={`${HEAD_CELL} text-right`}>As of</th>
                <th className={`${HEAD_CELL} text-right`}>
                  <span className="sr-only">Trade</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((h) => (
                <Row
                  key={h.ticker}
                  holding={h}
                  total={holdings?.totals.market_value ?? null}
                  onTrade={onTrade}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function Row({
  holding: h,
  total,
  onTrade,
}: {
  holding: Holding;
  total: number | null;
  onTrade: (ticker: string, type: "BUY" | "SELL") => void;
}) {
  const weight =
    h.market_value != null && total != null && total > 0
      ? (h.market_value / total) * 100
      : null;
  return (
    <tr className="holdings-row border-b border-line transition-colors last:border-0 hover:bg-panel-2">
      {/* .holdings-pin repaints the row's hover tint — see styles.css */}
      <td
        className={`holdings-pin ${STICKY} z-10 px-3 py-2.5 transition-colors sm:px-5`}
      >
        <Link to={`/stocks/${h.ticker}`} className="group flex flex-col">
          <span className="w-wide text-[13px] font-bold uppercase tracking-[0.06em] text-ink transition-colors group-hover:text-accent">
            {h.ticker}
          </span>
          <span className="max-w-[110px] truncate text-[11px] text-ink-3 sm:max-w-[220px]">
            {h.name}
          </span>
        </Link>
      </td>
      <td className="tnum px-3 py-2.5 sm:px-5 text-right ">{fmtNum(h.lots)}</td>
      <td className="tnum px-3 py-2.5 sm:px-5 text-right text-ink-2">
        {fmtRp(Math.round(h.avg_cost_per_share))}
      </td>
      {/* ink-2 like Avg cost beside it: both are what you paid, held back a
          step from the live figures they are read against. */}
      <td className="tnum px-3 py-2.5 sm:px-5 text-right text-ink-2">
        {fmtRp(h.cost_basis)}
      </td>
      <td className="tnum px-3 py-2.5 sm:px-5 text-right ">
        {fmtRp(h.last_price)}
      </td>
      <td className="tnum px-3 py-2.5 sm:px-5 text-right ">
        {fmtRp(h.market_value)}
      </td>
      <td className={`tnum px-3 py-2.5 sm:px-5 text-right ${signClass(h.unrealized_pnl)}`}>
        <span className="block">{fmtSignedRp(h.unrealized_pnl)}</span>
        <span className="block text-xs opacity-80">
          {h.unrealized_pnl_pct == null ? DASH : fmtPct(h.unrealized_pnl_pct, true)}
        </span>
      </td>
      <td className="px-3 py-2.5 sm:px-5">
        {weight == null ? (
          <span className="text-xs text-ink-3">{DASH}</span>
        ) : (
          <div className="flex items-center gap-2">
            {/* a square meter on a flat track — the system has no pills */}
            <div className="h-2 w-16 overflow-hidden bg-panel-2">
              <div
                className="h-full bg-accent"
                style={{ width: `${Math.min(100, weight)}%` }}
              />
            </div>
            <span className="tnum w-8 text-right text-[11px] text-ink-3">
              {weight.toFixed(0)}%
            </span>
          </div>
        )}
      </td>
      <td className="px-3 py-2.5 sm:px-5 text-right text-[11px] text-ink-3">
        {h.as_of
          ? fmtAsOf(h.as_of)
          : h.last_price != null && h.last_close_date
            ? `close, ${fmtDateShort(h.last_close_date)}`
            : DASH}
      </td>
      <td className="px-3 py-2.5 sm:px-5">
        {/* Buy and Sell are neutral, not green and red. A sell is not a loss,
            and the P&L column two cells left is already spending the signal
            colours on the only thing they may mean here — the sign of a
            value. Colouring the actions competed with it. */}
        <div className="flex justify-end gap-px">
          <button
            onClick={() => onTrade(h.ticker, "BUY")}
            className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-[0.1em] text-ink ring-1 ring-line-2 outline-none press hover:bg-ink hover:text-bg active:bg-ink active:text-bg focus-visible:ring-2 focus-visible:ring-accent"
          >
            Buy
          </button>
          <button
            onClick={() => onTrade(h.ticker, "SELL")}
            className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-[0.1em] text-ink ring-1 ring-line-2 outline-none press hover:bg-ink hover:text-bg active:bg-ink active:text-bg focus-visible:ring-2 focus-visible:ring-accent"
          >
            Sell
          </button>
        </div>
      </td>
    </tr>
  );
}
