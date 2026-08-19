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

type SortKey = "ticker" | "lots" | "cost_basis" | "last_price" | "market_value" | "unrealized_pnl";

/** Tighter cell padding on a phone: every 40px of chrome is a numeric column
 *  pushed off screen. */
const HEAD_CELL =
  "px-3 py-2.5 sm:px-5 text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3";

/** The ticker stays pinned while the figures scroll under it: without it you
 *  read a row of numbers with no idea which holding they belong to. The
 *  background must be opaque or the scrolled columns show through. */
const STICKY = "sticky left-0 border-r border-line bg-panel";

/** Every cell here holds two figures — a position total over the per-share
 *  number behind it — so every heading does too. The sub-label is what makes
 *  the folding legible: without it the second line is an unexplained number
 *  and the table reads as cramped rather than as two registers.
 *
 *  Only the top line sorts. The pair is one column, ordered by its total. */
const COLUMNS: {
  key: SortKey;
  label: string;
  sub?: string;
  align: "left" | "right";
}[] = [
  // Lot count rides under the code, which is where a broker's blotter puts it
  // and which buys back the width that allocation needs.
  { key: "ticker", label: "Code", sub: "Lot", align: "left" },
  { key: "cost_basis", label: "Invested", sub: "Avg price", align: "right" },
  // "Market", not "Value": paired against Invested the contrast is what the
  // number is measured by, not that one of them is the real one.
  { key: "market_value", label: "Market", sub: "Current price", align: "right" },
  { key: "unrealized_pnl", label: "P&L", sub: "Gain", align: "right" },
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
          title="No holdings yet" body="Record a buy and this table fills in." action={<Button onClick={onAddTransaction}>Add transaction</Button>}
        />
      ) : (
        // contain:paint keeps the wide table's overflow inside this scroller.
        // Without it the table's extent reaches the document and the whole
        // page scrolls sideways on a phone — overflow-x-auto alone does not
        // stop it here.
        <div className="overflow-x-auto pb-2 [contain:paint]">
          <table className="w-full min-w-[680px] text-[13px]">
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
                    {/* Outside the button on purpose: it names the second
                        line of the cell, which is not what sorting acts on. */}
                    {c.sub && (
                      <span className="mt-1 block font-normal opacity-60">
                        {c.sub}
                      </span>
                    )}
                  </th>
                ))}
                <th className={`${HEAD_CELL} text-left`}>Allocation</th>
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
          {/* Lot count first, company name after: the lot count is the figure
              this line is headed as, and the name is context. Truncating
              trims the name, never the number. */}
          {/* Capped tighter than the name alone used to be: this column is the
              table's widest, and the 30-odd pixels it gives up here are what
              keep the whole row inside a 1024px window. The name truncates;
              the lot count never does. */}
          <span className="max-w-[130px] truncate text-[11px] text-ink-3 sm:max-w-[205px]">
            <span className="tnum">{fmtNum(h.lots)} lot</span> · {h.name}
          </span>
        </Link>
      </td>
      {/* ink-2 throughout: what you paid, held a step back from the live
          figures it is read against. */}
      <td className="tnum px-3 py-2.5 sm:px-5 text-right text-ink-2">
        <span className="block">{fmtRp(h.cost_basis)}</span>
        <span className="block text-xs opacity-80">
          {fmtRp(Math.round(h.avg_cost_per_share))}
        </span>
      </td>
      <td className="tnum px-3 py-2.5 sm:px-5 text-right ">
        <span className="block">{fmtRp(h.market_value)}</span>
        <span className="block text-xs text-ink-3">{fmtRp(h.last_price)}</span>
      </td>
      <td className={`tnum px-3 py-2.5 sm:px-5 text-right ${signClass(h.unrealized_pnl)}`}>
        <span className="block">{fmtSignedRp(h.unrealized_pnl)}</span>
        <span className="block text-xs opacity-80">
          {h.unrealized_pnl_pct == null ? DASH : fmtPct(h.unrealized_pnl_pct, true)}
        </span>
      </td>
      {/* Back as its own column now that the lot count rides under the code.
          The donut beside this table is by SECTOR, so per-holding weight
          exists nowhere else on the page. */}
      <td className="px-3 py-2.5 sm:px-5">
        {weight == null ? (
          <span className="text-xs text-ink-3">{DASH}</span>
        ) : (
          <div className="flex items-center gap-2">
            {/* a square meter on a flat track — the system has no pills */}
            <div className="h-2 w-10 overflow-hidden bg-panel-2">
              <div
                className="h-full bg-accent"
                style={{ width: `${Math.min(100, weight)}%` }}
              />
            </div>
            <span className="tnum w-7 text-right text-[11px] text-ink-3">
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
