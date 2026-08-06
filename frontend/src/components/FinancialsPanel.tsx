import type { Financials, StatementPeriod } from "../api/client";
import { DASH, fmtDec, fmtNumCompact, fmtRpCompact } from "../lib/format";
import {
  EmptyState,
  ErrorNote,
  Panel,
  PanelHeader,
  Skeleton,
  WhatIsThis,
} from "./ui";

const periodLabel = new Intl.DateTimeFormat("id-ID", {
  month: "short",
  year: "2-digit",
});

/** Statement figures are in the issuer's reporting currency. */
export function FinancialsPanel({
  financials: f,
  loading,
  error,
}: {
  financials: Financials | null;
  loading: boolean;
  error?: string | null;
}) {
  if (error) {
    return (
      <Panel tone="flat">
        <PanelHeader seq="05" title="Financials" />
        <div className="px-5 pb-5">
          <ErrorNote message={error} />
        </div>
      </Panel>
    );
  }

  if (loading) {
    return (
      <Panel tone="flat">
        <PanelHeader seq="05" title="Financials" />
        <div className="space-y-2 px-5 pb-5">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-24 w-full" />
        </div>
      </Panel>
    );
  }

  if (!f || (f.annual.length === 0 && f.quarterly.length === 0)) {
    return (
      <Panel tone="flat">
        <PanelHeader seq="05" title="Financials" />
        <EmptyState
          title="No statements yet" body="Financial statements fetch on a ticker's first visit and refresh weekly. Yahoo carries none for some small caps."
        />
      </Panel>
    );
  }

  const cur = f.currency;
  const money = (v: number | null | undefined) => {
    if (v == null) return DASH;
    return cur && cur !== "IDR"
      ? `${cur} ${fmtNumCompact(v)}`
      : fmtRpCompact(v);
  };
  const eps = (v: number | null | undefined) => {
    if (v == null) return DASH;
    const s = v.toLocaleString("id-ID", { maximumFractionDigits: 2 });
    return cur && cur !== "IDR" ? `${cur} ${s}` : `Rp ${s}`;
  };
  const num = (v: number | null | undefined, suffix = "") =>
    v == null ? DASH : fmtDec(v) + suffix;
  const days = (v: number | null | undefined) =>
    v == null ? DASH : `${v.toLocaleString("id-ID")} days`;

  const d = f.derived;
  const groups: { title: string; rows: [string, string][] }[] = [
    {
      title: "Solvency & quality",
      rows: [
        ["Interest coverage (ttm)", num(d.interest_coverage, "×")],
        ["Financial leverage", num(d.financial_leverage, "×")],
        ["LT debt / equity", num(d.lt_debt_to_equity)],
        ["Liabilities / equity", num(d.liabilities_to_equity)],
        ["Debt / assets", num(d.debt_to_assets)],
        ["Altman Z'' (emerging)", num(d.altman_z)],
        [
          "Piotroski F-Score",
          d.piotroski_f != null
            ? `${d.piotroski_f} / ${d.piotroski_max ?? 9}`
            : DASH,
        ],
      ],
    },
    {
      title: "Efficiency",
      rows: [
        ["Return on capital employed", num(d.roce_pct, "%")],
        ["Asset turnover (ttm)", num(d.asset_turnover, "×")],
        ["Days sales outstanding", days(d.days_sales_outstanding)],
        ["Days inventory", days(d.days_inventory)],
        ["Days payables", days(d.days_payables)],
        ["Cash conversion cycle", days(d.cash_conversion_cycle)],
      ],
    },
    {
      title: "Cash flow (ttm, OCF − capex)",
      rows: [
        ["Free cash flow", money(d.fcf_ttm)],
        ["Price / free cash flow", num(d.price_to_fcf_ttm, "×")],
      ],
    },
  ];

  const tableRows: [string, string, boolean][] = [
    // label, item key, use eps formatting
    ["Revenue", "revenue", false],
    ["Gross profit", "gross_profit", false],
    ["Net income", "net_income", false],
    ["EPS (diluted)", "diluted_eps", true],
    ["Operating cash flow", "operating_cash_flow", false],
    ["Free cash flow", "free_cash_flow", false],
  ];

  const renderTable = (title: string, periods: StatementPeriod[]) => {
    if (periods.length === 0) return null;
    return (
      <div className="mt-5 border-t border-line pt-3">
        <p className="mb-2 text-xs font-medium text-ink-3">
          {title}
          {cur && cur !== "IDR" && ` (${cur})`}
        </p>
        {/* contain:paint keeps this wide table's overflow inside the scroller;
            without it the page itself scrolls sideways on a phone */}
        <div className="overflow-x-auto [contain:paint]">
          <table className="w-full min-w-[560px] text-[13px]">
            <thead>
              {/* the heavy rule under the heads matches the holdings table */}
              <tr className="w-wide border-b-2 border-ink text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
                <th scope="col" className="py-2 pr-4 text-left">
                  <span className="sr-only">Metric</span>
                </th>
                {periods.map((p) => (
                  <th
                    key={p.period_end}
                    scope="col" className="tnum py-2 pl-4 text-right"
                  >
                    {periodLabel.format(new Date(p.period_end))}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.map(([label, key, isEps]) => (
                <tr key={key} className="border-b border-line last:border-0">
                  <th
                    scope="row" className="py-2 pr-4 text-left font-normal text-ink-3"
                  >
                    {label}
                  </th>
                  {periods.map((p) => {
                    const v = p.items[key];
                    return (
                      <td
                        key={p.period_end}
                        className={`tnum py-1.5 pl-4 text-right ${
                          v != null && v < 0 ? "text-neg" : "text-ink"
                        }`}
                      >
                        {v == null ? DASH : isEps ? eps(v) : money(v)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <Panel tone="flat">
      <PanelHeader seq="05" title="Financials" />
      <div className="px-5 pb-5">
        <div className="grid grid-cols-1 gap-x-10 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
          {groups.map((g) => (
            <div key={g.title} className="border-t border-line pt-3">
              <p className="mb-2 text-xs font-medium text-ink-3">{g.title}</p>
              <dl className="flex flex-col gap-1.5 text-[13px]">
                {g.rows.map(([label, value]) => (
                  <div
                    key={label}
                    className="flex items-baseline justify-between gap-4"
                  >
                    <dt className="text-ink-3">{label}</dt>
                    <dd className="tnum text-ink">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>

        {renderTable("Quarterly", f.quarterly)}
        {renderTable("Annual", f.annual)}

        <div className="mt-5">
          <WhatIsThis label="solvency scores">
            <strong className="font-medium text-ink">Altman Z''</strong> is a
            bankruptcy-risk score for emerging markets: above about 5,85 is
            considered safe, below about 3,75 is distressed.{" "}
            <strong className="font-medium text-ink">Piotroski F-Score</strong>{" "}
            counts how many of nine accounting health checks a company passes —
            8–9 is strong, 0–2 is weak.{" "}
            <strong className="font-medium text-ink">Interest coverage</strong>{" "}
            is how many times over profit covers the interest bill.
          </WhatIsThis>
        </div>

        <p className="mt-3 text-xs text-ink-3">
          Statements from Yahoo (≈4 annual periods, ≈5 quarters), refreshed
          weekly. Derived metrics computed from these statements; free cash
          flow uses the OCF − capex convention.
        </p>
      </div>
    </Panel>
  );
}
