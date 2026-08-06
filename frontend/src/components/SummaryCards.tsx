import type { Holdings, Metrics } from "../api/client";
import {
  DASH,
  fmtAsOf,
  fmtDec,
  fmtPct,
  fmtRp,
  fmtSignedRp,
  signClass,
} from "../lib/format";
import { Skeleton } from "./ui";

/** One figure in the supporting row. Cells sit on a hairline bed and paint
 *  their own background, so the gaps themselves draw the rules — no per-cell
 *  borders to keep in sync as cells appear and disappear.
 *
 *  They FLEX rather than sitting in fixed grid tracks, and that is load-
 *  bearing: Realized P&L and Cash are conditional, so a fixed 3-column grid
 *  leaves 1–2 empty tracks on the last row with no cell to paint them, and
 *  the bed shows through as a grey block. Growing to fill the row means the
 *  bed is only ever visible as the 1px gaps it is meant to be. */
function Cell({
  label,
  value,
  tone = "text-ink",
  note,
  noteTone = "text-ink-3",
}: {
  label: string;
  value: string;
  tone?: string;
  note?: string;
  noteTone?: string;
}) {
  return (
    <div className="flex-1 basis-[190px] bg-bg px-4 py-4">
      <dt className="w-wide text-[10px] font-bold uppercase leading-none tracking-[0.14em] text-ink-3">
        {label}
      </dt>
      <dd className={`tnum mt-2.5 text-[22px] font-bold leading-none ${tone}`}>
        {value}
      </dd>
      {note && (
        <dd className={`tnum mt-2 text-[11px] leading-tight ${noteTone}`}>{note}</dd>
      )}
    </div>
  );
}

/** The portfolio's worth is the page's poster figure — knocked out of a flat
 *  field of the accent, with the supporting figures ruled off beside it. This
 *  is the one place per page where the accent takes a whole surface. */
export function SummaryCards({
  holdings,
  metrics,
  loading,
}: {
  holdings: Holdings | null;
  metrics: Metrics | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="grid gap-px bg-line lg:grid-cols-[minmax(300px,0.9fr)_1.5fr]">
        <Skeleton className="h-[168px]" />
        <div className="flex flex-wrap gap-px bg-line">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-[86px] flex-1 basis-[190px]" />
          ))}
        </div>
      </div>
    );
  }

  const totals = holdings?.totals;
  const newestAsOf = holdings?.holdings.reduce<string | null>(
    (acc, h) => (h.as_of && (!acc || h.as_of > acc) ? h.as_of : acc),
    null,
  );
  // Total return weighs every holding by the rupiah behind it — aggregating
  // amounts does that by construction, where averaging the per-row percentages
  // would let a tiny position swing the number as hard as a large one.
  // Denominator is all capital committed to positions, open and closed, so
  // taking a profit cannot make the figure worse.
  const investedCost = totals ? totals.cost_basis + totals.realized_cost_basis : 0;
  const totalReturnRp =
    totals && totals.unrealized_pnl != null
      ? totals.unrealized_pnl + totals.realized_pnl
      : null;
  const totalReturnPct =
    totalReturnRp != null && investedCost > 0
      ? (totalReturnRp / investedCost) * 100
      : null;

  const vsIhsg =
    metrics &&
    metrics.total_return_pct != null &&
    metrics.benchmark_return_pct != null
      ? metrics.total_return_pct - metrics.benchmark_return_pct
      : null;

  return (
    <div className="grid gap-px bg-line lg:grid-cols-[minmax(300px,0.9fr)_1.5fr]">
      {/* the poster figure: a flat field of accent, knockout and condensed */}
      {/* quick, not focal: this is seen every time a portfolio is opened,
          where the login's 750ms wipe is seen once per session */}
      <div className="field-wipe-quick flex flex-col justify-between gap-8 bg-accent px-6 py-6 text-on-accent">
        <p className="w-wide text-[10px] font-bold uppercase leading-none tracking-[0.16em] text-on-accent/75">
          Total value
        </p>
        <div>
          <p className="tnum w-condensed break-words text-[clamp(2.5rem,5.5vw,3.5rem)] font-extrabold leading-[0.88] tracking-[-0.03em]">
            {fmtRp(totals?.market_value)}
          </p>
          <p className="tnum mt-3 text-[11px] text-on-accent/75">
            {totals && totals.unpriced_holdings > 0
              ? `${totals.unpriced_holdings} holding(s) unpriced`
              : newestAsOf
                ? `as of ${fmtAsOf(newestAsOf)}`
                : totals?.market_value != null
                  ? "at last close"
                  : "no priced holdings yet"}
          </p>
        </div>
      </div>

      {/* supporting figures, on the hairline bed */}
      <dl className="flex flex-wrap gap-px bg-line">
        {/* the summary the two P&L figures below break down */}
        <Cell
          label="Total return"
          value={totalReturnPct == null ? DASH : fmtPct(totalReturnPct, true)}
          tone={signClass(totalReturnPct)}
          note={
            totalReturnRp == null
              ? "appears once a holding is priced"
              : `${fmtSignedRp(totalReturnRp)} on ${fmtRp(investedCost)} invested`
          }
        />
        <Cell
          label="Unrealized P&L"
          value={fmtSignedRp(totals?.unrealized_pnl)}
          tone={signClass(totals?.unrealized_pnl)}
          // the cost it is measured against, not a second return percentage
          // competing with Total return above
          note={totals ? `on ${fmtRp(totals.cost_basis)} cost` : DASH}
        />
        {totals != null && totals.realized_pnl !== 0 && (
          <Cell
            label="Realized P&L"
            value={fmtSignedRp(totals.realized_pnl)}
            tone={signClass(totals.realized_pnl)}
            note="locked in by sells"
          />
        )}
        {totals != null && (
          <Cell
            label="Cash"
            value={fmtRp(totals.cash_balance)}
            // "deposits minus trades" is not true when trades predate the
            // first cash flow — the balance silently skips those
            note={
              !totals.cash_tracked
                ? "deposit before buying"
                : totals.cash_uncounted_trades > 0
                  ? `${totals.cash_uncounted_trades} earlier trade${totals.cash_uncounted_trades > 1 ? "s" : ""} not counted — see Cash`
                  : "deposits minus trades"
            }
            noteTone={totals.cash_uncounted_trades > 0 ? "text-warn" : "text-ink-3"}
          />
        )}
        <Cell
          label={`vs IHSG (${metrics?.range ?? DASH})`}
          value={
            vsIhsg == null ? DASH : `${vsIhsg > 0 ? "+" : ""}${fmtDec(vsIhsg)} pp`
          }
          tone={signClass(vsIhsg)}
          // naming the method: deposits never masquerade as gains here
          note={
            metrics && metrics.total_return_pct != null
              ? `you ${fmtPct(metrics.total_return_pct, true)} · IHSG ${fmtPct(metrics.benchmark_return_pct, true)} · time-weighted`
              : "appears after your first transaction"
          }
        />
      </dl>
    </div>
  );
}
