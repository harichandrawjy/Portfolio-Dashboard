"""Financial statements from yfinance (Tier 2 fundamentals).

Fetches annual + quarterly income statement, balance sheet, and cash flow
per ticker, keeps a whitelisted set of line items, and stores one JSONB
row per (security, period_type, period_end). Values are floats in the
issuer's reporting currency (IDR or USD on IDX).

Derived metrics (interest coverage, cash-conversion cycle, Altman Z'',
Piotroski F, honest OCF-minus-capex free cash flow, ...) are computed by
the PURE function compute_derived() below — at request time, because the
math is a handful of dict lookups over <=10 rows, unlike the price-series
scans that justify the security_stats cache.

Honesty notes:
  - Yahoo's statement depth is ~4 annual periods and ~5 quarters; a full
    multi-year quarterly grid like brokers show needs licensed data.
  - Small-cap coverage is patchy; every metric degrades to None.
  - Altman Z'' is the emerging-markets variant (Z'' = 6.56*X1 + 3.26*X2
    + 6.72*X3 + 1.05*X4) with TTM EBIT; Piotroski uses the two newest
    annual periods and reports how many of the 9 signals were evaluable.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import yfinance as yf
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import FinancialStatement, PriceHistory, Security
from app.sync.prices import REQUEST_PAUSE, RETRY_ATTEMPTS, RETRY_BASE_DELAY

logger = logging.getLogger(__name__)

# our key -> Yahoo row labels, first match wins
LINE_ITEMS: dict[str, tuple[str, ...]] = {
    # income statement
    "revenue": ("Total Revenue", "Operating Revenue"),
    "gross_profit": ("Gross Profit",),
    "operating_income": ("Operating Income",),
    "ebit": ("EBIT",),
    "ebitda": ("EBITDA", "Normalized EBITDA"),
    "interest_expense": ("Interest Expense",),
    "net_income": ("Net Income", "Net Income Common Stockholders"),
    "diluted_eps": ("Diluted EPS",),
    "basic_eps": ("Basic EPS",),
    # balance sheet
    "total_assets": ("Total Assets",),
    "total_liabilities": ("Total Liabilities Net Minority Interest",),
    "stockholders_equity": (
        "Stockholders Equity",
        "Total Equity Gross Minority Interest",
    ),
    "current_assets": ("Current Assets",),
    "current_liabilities": ("Current Liabilities",),
    "inventory": ("Inventory",),
    "receivables": ("Accounts Receivable", "Receivables"),
    "payables": ("Accounts Payable", "Payables"),
    "cash_and_equivalents": (
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
    ),
    "current_debt": ("Current Debt", "Current Debt And Capital Lease Obligation"),
    "long_term_debt": (
        "Long Term Debt",
        "Long Term Debt And Capital Lease Obligation",
    ),
    "total_debt": ("Total Debt",),
    "working_capital": ("Working Capital",),
    "retained_earnings": ("Retained Earnings",),
    "shares_issued": ("Ordinary Shares Number", "Share Issued"),
    # cash flow
    "operating_cash_flow": (
        "Operating Cash Flow",
        # some IDX issuers file a direct-method quarterly cash-flow statement
        "Cash Flow From Continuing Operating Activities",
        "Cash Flowsfromusedin Operating Activities Direct",
    ),
    "investing_cash_flow": ("Investing Cash Flow",),
    "financing_cash_flow": ("Financing Cash Flow",),
    "capital_expenditure": ("Capital Expenditure",),
    "free_cash_flow": ("Free Cash Flow",),
}


@dataclass
class StatementsResult:
    synced: int = 0
    periods: int = 0
    failed: list[str] = field(default_factory=list)


def _merge_frame(frame, merged: dict[date, dict]) -> None:
    if frame is None or getattr(frame, "empty", True):
        return
    for col in frame.columns:
        period = col.date() if hasattr(col, "date") else None
        if period is None:
            continue
        bucket = merged.setdefault(period, {})
        for our_key, labels in LINE_ITEMS.items():
            if our_key in bucket:
                continue
            for label in labels:
                if label in frame.index:
                    value = frame.at[label, col]
                    if value is not None and not pd.isna(value):
                        bucket[our_key] = float(value)
                        break


def _fetch_statements(symbol: str) -> dict[tuple[str, date], dict]:
    """{(period_type, period_end): items} — retried as a whole."""
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            t = yf.Ticker(symbol)
            out: dict[tuple[str, date], dict] = {}
            for period_type, frames in (
                ("annual", (t.income_stmt, t.balance_sheet, t.cashflow)),
                (
                    "quarterly",
                    (
                        t.quarterly_income_stmt,
                        t.quarterly_balance_sheet,
                        t.quarterly_cashflow,
                    ),
                ),
            ):
                merged: dict[date, dict] = {}
                for frame in frames:
                    _merge_frame(frame, merged)
                for period, items in merged.items():
                    if items:
                        out[(period_type, period)] = items
            return out
        except Exception as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS:
                delay = RETRY_BASE_DELAY * 2 ** (attempt - 1) * random.uniform(0.8, 1.2)
                logger.warning(
                    "Yahoo statements %s failed (attempt %d/%d): %s — retrying in %.1fs",
                    symbol, attempt, RETRY_ATTEMPTS, exc, delay,
                )
                time.sleep(delay)
    raise last_exc  # type: ignore[misc]


async def sync_statements(tickers: list[str] | None = None) -> StatementsResult:
    """Refresh statements for tracked tickers (or an explicit list)."""
    async with SessionLocal() as session:
        stmt = (
            select(Security)
            .join(PriceHistory, PriceHistory.security_id == Security.id)
            .where(Security.kind == "stock")
            .distinct()
            .order_by(Security.ticker)
        )
        if tickers is not None:
            stmt = stmt.where(Security.ticker.in_([t.strip().upper() for t in tickers]))
        secs = list(await session.scalars(stmt))

    result = StatementsResult()
    for i, sec in enumerate(secs):
        if i:
            await asyncio.sleep(REQUEST_PAUSE)
        try:
            periods = await asyncio.to_thread(_fetch_statements, sec.yahoo_symbol)
            async with SessionLocal() as session:
                async with session.begin():
                    for (period_type, period_end), items in periods.items():
                        ins = pg_insert(FinancialStatement).values(
                            security_id=sec.id,
                            period_type=period_type,
                            period_end=period_end,
                            items=items,
                            fetched_at=func.now(),
                        )
                        ins = ins.on_conflict_do_update(
                            index_elements=["security_id", "period_type", "period_end"],
                            set_={"items": items, "fetched_at": func.now()},
                        )
                        await session.execute(ins)
            logger.info(
                "statements %s: %d period(s)", sec.ticker, len(periods)
            )
            result.synced += 1
            result.periods += len(periods)
        except Exception:
            logger.exception("statements failed for %s — continuing", sec.ticker)
            result.failed.append(sec.ticker)

    logger.info(
        "statements sync: %d synced (%d periods), %d failed%s",
        result.synced, result.periods, len(result.failed),
        f" ({', '.join(result.failed)})" if result.failed else "",
    )
    return result


# ---------------------------------------------------------------------------
# Pure derivations (unit-tested with hand-computed values)
# ---------------------------------------------------------------------------

DAYS_PER_QUARTER = 91.25


def _ttm(quarters: list[dict], keys: str | tuple[str, ...]) -> float | None:
    """Sum of four quarterly values taken from the newest five periods.

    Yahoo's quarterly frames routinely miss one period (cash-flow data
    lags a quarter; EBIT rows drop out), so the window is five with four
    values required. `keys` may list fallbacks tried per quarter (e.g.
    operating income when EBIT is absent).
    """
    if isinstance(keys, str):
        keys = (keys,)
    values: list[float] = []
    for q in quarters[:5]:
        for key in keys:
            if q.get(key) is not None:
                values.append(q[key])
                break
        if len(values) == 4:
            break
    return sum(values) if len(values) == 4 else None


def compute_derived(
    quarterly: list[dict],
    annual: list[dict],
    market_cap: int | None,
    idr_reporter: bool,
) -> dict:
    """Solvency/efficiency/quality metrics from statement items.

    quarterly/annual are item dicts NEWEST FIRST. All ratios None-degrade.
    """
    d: dict = {}
    latest = quarterly[0] if quarterly else {}

    revenue_ttm = _ttm(quarterly, "revenue")
    ebit_ttm = _ttm(quarterly, ("ebit", "operating_income"))
    interest_ttm = _ttm(quarterly, "interest_expense")
    ocf_ttm = _ttm(quarterly, "operating_cash_flow")
    capex_ttm = _ttm(quarterly, "capital_expenditure")

    total_assets = latest.get("total_assets")
    equity = latest.get("stockholders_equity")
    liabilities = latest.get("total_liabilities")
    current_assets = latest.get("current_assets")
    current_liabilities = latest.get("current_liabilities")

    if ebit_ttm is not None and interest_ttm:
        d["interest_coverage"] = round(ebit_ttm / abs(interest_ttm), 2)
    if total_assets and equity:
        d["financial_leverage"] = round(total_assets / equity, 2)
    lt_debt = latest.get("long_term_debt")
    if lt_debt is not None and equity:
        d["lt_debt_to_equity"] = round(lt_debt / equity, 2)
    if liabilities is not None and equity:
        d["liabilities_to_equity"] = round(liabilities / equity, 2)
    total_debt = latest.get("total_debt")
    if total_debt is not None and total_assets:
        d["debt_to_assets"] = round(total_debt / total_assets, 2)
    if revenue_ttm and total_assets:
        d["asset_turnover"] = round(revenue_ttm / total_assets, 2)
    if (
        ebit_ttm is not None
        and total_assets
        and current_liabilities is not None
        and total_assets - current_liabilities
    ):
        d["roce_pct"] = round(ebit_ttm / (total_assets - current_liabilities) * 100, 2)

    # working-capital days off the latest quarter
    revenue_q = latest.get("revenue")
    gross_q = latest.get("gross_profit")
    cogs_q = (
        revenue_q - gross_q if revenue_q is not None and gross_q is not None else None
    )
    receivables = latest.get("receivables")
    inventory = latest.get("inventory")
    payables = latest.get("payables")
    if receivables is not None and revenue_q:
        d["days_sales_outstanding"] = round(
            receivables / (revenue_q / DAYS_PER_QUARTER), 1
        )
    if inventory is not None and cogs_q:
        d["days_inventory"] = round(inventory / (cogs_q / DAYS_PER_QUARTER), 1)
    if payables is not None and cogs_q:
        d["days_payables"] = round(payables / (cogs_q / DAYS_PER_QUARTER), 1)
    if all(k in d for k in ("days_sales_outstanding", "days_inventory", "days_payables")):
        d["cash_conversion_cycle"] = round(
            d["days_sales_outstanding"] + d["days_inventory"] - d["days_payables"], 1
        )

    # free cash flow, OCF - |capex| convention (capex arrives negative);
    # fall back to Yahoo's own per-quarter free cash flow when the direct
    # OCF is unavailable for four quarters
    fcf = None
    if ocf_ttm is not None and capex_ttm is not None:
        fcf = ocf_ttm - abs(capex_ttm)
    else:
        fcf = _ttm(quarterly, "free_cash_flow")
    if fcf is not None:
        d["fcf_ttm"] = round(fcf)
        if idr_reporter and market_cap and fcf > 0:
            d["price_to_fcf_ttm"] = round(market_cap / fcf, 2)

    # Altman Z'' (emerging markets): 6.56*WC/TA + 3.26*RE/TA
    #                                + 6.72*EBIT/TA + 1.05*BVE/TL
    working_capital = latest.get("working_capital")
    if working_capital is None and None not in (current_assets, current_liabilities):
        working_capital = current_assets - current_liabilities  # type: ignore[operator]
    retained = latest.get("retained_earnings")
    if (
        total_assets
        and liabilities
        and equity is not None
        and None not in (working_capital, retained, ebit_ttm)
    ):
        z = (
            6.56 * working_capital / total_assets  # type: ignore[operator]
            + 3.26 * retained / total_assets  # type: ignore[operator]
            + 6.72 * ebit_ttm / total_assets  # type: ignore[operator]
            + 1.05 * equity / liabilities
        )
        d["altman_z"] = round(z, 2)

    # Piotroski F-Score from the two newest annual periods
    if len(annual) >= 2:
        cur, prev = annual[0], annual[1]
        signals: list[bool] = []

        def _roa(x: dict) -> float | None:
            ni, ta = x.get("net_income"), x.get("total_assets")
            return ni / ta if ni is not None and ta else None

        def _ratio(x: dict, num: str, den: str) -> float | None:
            n, dd = x.get(num), x.get(den)
            return n / dd if n is not None and dd else None

        roa_now, roa_prev = _roa(cur), _roa(prev)
        ocf_a = cur.get("operating_cash_flow")
        ni_a = cur.get("net_income")
        if roa_now is not None:
            signals.append(roa_now > 0)
        if ocf_a is not None:
            signals.append(ocf_a > 0)
        if roa_now is not None and roa_prev is not None:
            signals.append(roa_now > roa_prev)
        if ocf_a is not None and ni_a is not None:
            signals.append(ocf_a > ni_a)
        lev_now = _ratio(cur, "long_term_debt", "total_assets")
        lev_prev = _ratio(prev, "long_term_debt", "total_assets")
        if lev_now is not None and lev_prev is not None:
            signals.append(lev_now <= lev_prev)
        cr_now = _ratio(cur, "current_assets", "current_liabilities")
        cr_prev = _ratio(prev, "current_assets", "current_liabilities")
        if cr_now is not None and cr_prev is not None:
            signals.append(cr_now > cr_prev)
        sh_now, sh_prev = cur.get("shares_issued"), prev.get("shares_issued")
        if sh_now is not None and sh_prev is not None:
            signals.append(sh_now <= sh_prev)
        gm_now = _ratio(cur, "gross_profit", "revenue")
        gm_prev = _ratio(prev, "gross_profit", "revenue")
        if gm_now is not None and gm_prev is not None:
            signals.append(gm_now > gm_prev)
        at_now = _ratio(cur, "revenue", "total_assets")
        at_prev = _ratio(prev, "revenue", "total_assets")
        if at_now is not None and at_prev is not None:
            signals.append(at_now > at_prev)

        if signals:
            d["piotroski_f"] = sum(signals)
            d["piotroski_max"] = len(signals)

    return d
