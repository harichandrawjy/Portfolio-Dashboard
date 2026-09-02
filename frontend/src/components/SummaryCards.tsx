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
  //
  // The denominator is NET DEPOSITS: money that actually crossed in from
  // outside. It used to be cost_basis + realized_cost_basis, the sum of every
  // purchase ever made, which double-counts recycled capital — buying PANI
  // for ~50jt, selling it, and buying ESSA with the proceeds reported ~98jt
  // "committed" against a single 50jt deposit and halved the percentage. A
  // portfolio that round-trips the same money ten times read a tenth of its
  // real return, which is worst for exactly the short-term portfolios most
  // likely to do it.
  //
  // Committed capital stays as the fallback for portfolios with no cash
  // ledger, where net deposits is 0 and dividing by it would be undefined.
  const committed = totals ? totals.cost_basis + totals.realized_cost_basis : 0;
  const usingDeposits = !!totals && totals.net_deposits > 0;
  const returnBase = usingDeposits ? totals.net_deposits : committed;
  const totalReturnRp =
    totals && totals.unrealized_pnl != null
      ? totals.unrealized_pnl + totals.realized_pnl
      : null;
  const totalReturnPct =
    totalReturnRp != null && returnBase > 0
      ? (totalReturnRp / returnBase) * 100
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

          {/* What the holdings cost, set against what they are worth — the
              comparison every figure on the row to the right is derived from.
              It belongs inside the accent field rather than beside it: as a
              sixth cell it read as one more metric among many, when it is
              actually the other half of the poster figure.

              `cost_basis`, deliberately not cost_basis + realized_cost_basis.
              The poster is the market value of what is HELD, so its
              counterpart must be what THAT cost; folding in closed positions
              would measure today's holdings against capital already returned
              to cash. Total return, to the right, is the figure that does
              want the wider denominator. */}
          <div className="mt-6 border-t border-on-accent/25 pt-4">
            <p className="w-wide text-[10px] font-bold uppercase leading-none tracking-[0.16em] text-on-accent/75">
              Invested
            </p>
            <p className="tnum mt-2 text-[22px] font-bold leading-none">
              {fmtRp(totals?.cost_basis)}
            </p>
          </div>
        </div>
      </div>

      {/* supporting figures, on the hairline bed */}
      <dl className="flex flex-wrap gap-px bg-line">
        {/* the summary the two P&L figures below break down */}
        <Cell
          label="Total return"
          value={totalReturnPct == null ? DASH : fmtPct(totalReturnPct, true)}
          tone={signClass(totalReturnPct)}
          // "committed", not "invested". This denominator includes closed
          // positions, so it is a LARGER number than the Invested cell
          // alongside — two adjacent figures both labelled "invested" and
          // disagreeing reads as a bug rather than as the deliberate
          // distinction it is.
          note={
            totalReturnRp == null
              ? "appears once a holding is priced"
              : usingDeposits
                ? `${fmtSignedRp(totalReturnRp)} on ${fmtRp(returnBase)} deposited`
                : `${fmtSignedRp(totalReturnRp)} on ${fmtRp(returnBase)} committed, incl. closed`
          }
        />
        <Cell
          label="Unrealized P&L"
          value={fmtSignedRp(totals?.unrealized_pnl)}
          tone={signClass(totals?.unrealized_pnl)}
          // Was `on {cost_basis} cost` — now that Invested prints that exact
          // rupiah figure two cells away, repeating it made the row look like
          // it had miscounted. Says what the number covers instead; still not
          // a second percentage competing with Total return above.
          note={totals ? "open positions, at market" : DASH}
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
                  ? `${totals.cash_uncounted_trades} earlier trade${totals.cash_uncounted_trades > 1 ? "s" : ""} not counted (see Cash)`
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
