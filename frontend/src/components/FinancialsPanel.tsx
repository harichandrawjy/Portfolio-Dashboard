import type { Financials, StatementPeriod } from "../api/client";
import { DASH, fmtNumCompact, fmtRpCompact } from "../lib/format";
import { EmptyState, Panel, PanelHeader, Skeleton } from "./ui";

const periodLabel = new Intl.DateTimeFormat("id-ID", {
  month: "short",
  year: "2-digit",
});

/** Statement figures are in the issuer's reporting currency. */
export function FinancialsPanel({
  financials: f,
  loading,
}: {
  financials: Financials | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Panel tone="flat">
        <PanelHeader title="Financials" />
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
        <PanelHeader title="Financials" />
        <EmptyState
          title="No statements yet"
          body="Financial statements fetch on a ticker's first visit and refresh weekly. Yahoo carries none for some small caps."
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
    v == null ? DASH : v.toFixed(2) + suffix;
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
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-[13px]">
            <thead>
              <tr className="border-b border-line text-xs text-ink-3">
                <th className="py-1.5 pr-4 text-left font-medium"> </th>
                {periods.map((p) => (
                  <th
                    key={p.period_end}
                    className="tnum py-1.5 pl-4 text-right font-mono font-medium"
                  >
                    {periodLabel.format(new Date(p.period_end))}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.map(([label, key, isEps]) => (
                <tr key={key} className="border-b border-line/50 last:border-0">
                  <td className="py-1.5 pr-4 text-ink-3">{label}</td>
                  {periods.map((p) => {
                    const v = p.items[key];
                    return (
                      <td
                        key={p.period_end}
                        className={`tnum py-1.5 pl-4 text-right font-mono ${
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
      <PanelHeader title="Financials" />
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
                    <dd className="tnum font-mono text-ink">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>

        {renderTable("Quarterly", f.quarterly)}
        {renderTable("Annual", f.annual)}

        <p className="mt-5 text-xs text-ink-3">
          Statements from Yahoo (≈4 annual periods, ≈5 quarters), refreshed
          weekly. Derived metrics computed from these statements; free cash
          flow uses the OCF − capex convention.
        </p>
      </div>
    </Panel>
  );
}
