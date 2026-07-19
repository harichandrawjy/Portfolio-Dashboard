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
import { Button, EmptyState, Panel, PanelHeader, Skeleton } from "./ui";

type SortKey = "ticker" | "lots" | "avg_cost_per_share" | "last_price" | "market_value" | "unrealized_pnl";

const COLUMNS: { key: SortKey; label: string; align: "left" | "right" }[] = [
  { key: "ticker", label: "Ticker", align: "left" },
  { key: "lots", label: "Lots", align: "right" },
  { key: "avg_cost_per_share", label: "Avg cost", align: "right" },
  { key: "last_price", label: "Last price", align: "right" },
  { key: "market_value", label: "Value", align: "right" },
  { key: "unrealized_pnl", label: "P&L", align: "right" },
];

export function HoldingsTable({
  holdings,
  loading,
  onAddTransaction,
}: {
  holdings: Holdings | null;
  loading: boolean;
  onAddTransaction: () => void;
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

      {loading ? (
        <div className="space-y-2 px-5 pb-5">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<ChartLine size={28} weight="light" />}
          title="No holdings yet"
          body="Record your first buy to see value, P&L, and allocation for this portfolio."
          action={<Button onClick={onAddTransaction}>Add transaction</Button>}
        />
      ) : (
        <div className="overflow-x-auto pb-2">
          <table className="w-full min-w-[720px] text-[13px]">
            <thead>
              <tr className="border-b border-line text-left text-xs text-ink-3">
                {COLUMNS.map((c) => (
                  <th
                    key={c.key}
                    className={`px-5 py-2 font-medium ${c.align === "right" ? "text-right" : ""}`}
                  >
                    <button
                      onClick={() => toggleSort(c.key)}
                      className={`inline-flex items-center gap-1 hover:text-ink-2 ${
                        c.align === "right" ? "flex-row-reverse" : ""
                      } ${sortKey === c.key ? "text-ink-2" : ""}`}
                    >
                      {c.label}
                      {sortKey === c.key &&
                        (sortDir === "asc" ? (
                          <CaretUp size={11} weight="bold" />
                        ) : (
                          <CaretDown size={11} weight="bold" />
                        ))}
                    </button>
                  </th>
                ))}
                <th className="px-5 py-2 text-right text-xs font-medium">As of</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((h) => (
                <Row key={h.ticker} holding={h} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function Row({ holding: h }: { holding: Holding }) {
  return (
    <tr className="border-b border-line/50 transition-colors last:border-0 hover:bg-ink/[0.03]">
      <td className="px-5 py-2.5">
        <Link to={`/stocks/${h.ticker}`} className="group flex flex-col">
          <span className="font-mono text-sm font-semibold text-ink group-hover:text-accent">
            {h.ticker}
          </span>
          <span className="max-w-[220px] truncate text-xs text-ink-3">
            {h.name}
          </span>
        </Link>
      </td>
      <td className="tnum px-5 py-2.5 text-right font-mono">{fmtNum(h.lots)}</td>
      <td className="tnum px-5 py-2.5 text-right font-mono text-ink-2">
        {fmtRp(Math.round(h.avg_cost_per_share))}
      </td>
      <td className="tnum px-5 py-2.5 text-right font-mono">
        {fmtRp(h.last_price)}
      </td>
      <td className="tnum px-5 py-2.5 text-right font-mono">
        {fmtRp(h.market_value)}
      </td>
      <td className={`tnum px-5 py-2.5 text-right font-mono ${signClass(h.unrealized_pnl)}`}>
        <span className="block">{fmtSignedRp(h.unrealized_pnl)}</span>
        <span className="block text-xs opacity-80">
          {h.unrealized_pnl_pct == null ? DASH : fmtPct(h.unrealized_pnl_pct, true)}
        </span>
      </td>
      <td className="px-5 py-2.5 text-right text-xs text-ink-3">
        {h.as_of
          ? fmtAsOf(h.as_of)
          : h.last_price != null && h.last_close_date
            ? `close, ${fmtDateShort(h.last_close_date)}`
            : DASH}
      </td>
    </tr>
  );
}
