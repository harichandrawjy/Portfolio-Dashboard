"""Financial statements: pure derivations (hand-computed), sync, endpoint.

Derivation fixture — four quarters, NEWEST FIRST. Flow items exist in all
four; balance items only in the newest (that's how they're used):

  revenue          130, 120, 110, 100     -> TTM 460
  gross profit      52 (newest; COGS_q = 130-52 = 78)
  EBIT              13,  12,  11,  10     -> TTM 46
  interest expense   2,   2,   2,   2     -> TTM 8
  operating CF      20,  20,  20,  20     -> TTM 80
  capex             -5,  -5,  -5,  -5     -> TTM -20

  newest-quarter balance sheet:
  total assets 1000 · equity 500 · liabilities 500 · current assets 400
  current liabilities 200 · inventory 50 · receivables 40 · payables 30
  LT debt 100 · total debt 150 · retained earnings 300

Hand-computed expectations:
  interest coverage  46 / 8                        = 5.75
  financial leverage 1000 / 500                    = 2.00
  LT debt/equity     100 / 500                     = 0.20
  liabilities/equity 500 / 500                     = 1.00
  debt/assets        150 / 1000                    = 0.15
  asset turnover     460 / 1000                    = 0.46
  ROCE               46 / (1000-200)               = 5.75%
  DSO   40 / (130/91.25)                           = 28.1 days
  DIO   50 / (78/91.25)                            = 58.5 days
  DPO   30 / (78/91.25)                            = 35.1 days
  CCC   28.1 + 58.5 - 35.1                         = 51.5 days
  FCF (ttm)  80 - |-20|                            = 60
  P/FCF      market cap 600 / 60                   = 10.0
  Altman Z'' 6.56*(200/1000) + 3.26*(300/1000)
             + 6.72*(46/1000) + 1.05*(500/500)     = 3.65
"""

from datetime import date

import pytest

from tests.helpers import register_verified

from app.sync.statements import compute_derived

pytestmark = pytest.mark.asyncio(loop_scope="session")

QUARTERS = [
    {  # newest — carries the balance sheet
        "revenue": 130, "gross_profit": 52, "ebit": 13, "interest_expense": 2,
        "operating_cash_flow": 20, "capital_expenditure": -5,
        "total_assets": 1000, "stockholders_equity": 500,
        "total_liabilities": 500, "current_assets": 400,
        "current_liabilities": 200, "inventory": 50, "receivables": 40,
        "payables": 30, "long_term_debt": 100, "total_debt": 150,
        "retained_earnings": 300,
    },
    {"revenue": 120, "ebit": 12, "interest_expense": 2,
     "operating_cash_flow": 20, "capital_expenditure": -5},
    {"revenue": 110, "ebit": 11, "interest_expense": 2,
     "operating_cash_flow": 20, "capital_expenditure": -5},
    {"revenue": 100, "ebit": 10, "interest_expense": 2,
     "operating_cash_flow": 20, "capital_expenditure": -5},
]

# Piotroski: current year improves on almost everything except asset
# turnover (1.00 now vs 950/900 = 1.056 before) -> 8 of 9 signals
ANNUAL = [
    {"net_income": 50, "total_assets": 1000, "operating_cash_flow": 60,
     "long_term_debt": 100, "current_assets": 400, "current_liabilities": 200,
     "shares_issued": 1000, "gross_profit": 400, "revenue": 1000},
    {"net_income": 40, "total_assets": 900, "operating_cash_flow": 30,
     "long_term_debt": 150, "current_assets": 300, "current_liabilities": 200,
     "shares_issued": 1000, "gross_profit": 330, "revenue": 950},
]


async def test_derived_metrics_hand_checked():
    d = compute_derived(QUARTERS, ANNUAL, market_cap=600, idr_reporter=True)

    assert d["interest_coverage"] == pytest.approx(5.75)
    assert d["financial_leverage"] == pytest.approx(2.0)
    assert d["lt_debt_to_equity"] == pytest.approx(0.2)
    assert d["liabilities_to_equity"] == pytest.approx(1.0)
    assert d["debt_to_assets"] == pytest.approx(0.15)
    assert d["asset_turnover"] == pytest.approx(0.46)
    assert d["roce_pct"] == pytest.approx(5.75)
    assert d["days_sales_outstanding"] == pytest.approx(28.1)
    assert d["days_inventory"] == pytest.approx(58.5)
    assert d["days_payables"] == pytest.approx(35.1)
    assert d["cash_conversion_cycle"] == pytest.approx(51.5)
    assert d["fcf_ttm"] == 60
    assert d["price_to_fcf_ttm"] == pytest.approx(10.0)
    assert d["altman_z"] == pytest.approx(3.65)
    assert d["piotroski_f"] == 8
    assert d["piotroski_max"] == 9


async def test_derived_degrades_and_guards():
    # only three quarters -> no TTM figures, no crash
    d = compute_derived(QUARTERS[:3], [], market_cap=600, idr_reporter=True)
    assert "interest_coverage" not in d
    assert "fcf_ttm" not in d
    # balance-sheet-only ratios still work off the newest quarter
    assert d["financial_leverage"] == pytest.approx(2.0)

    # USD reporter: FCF is fine (own currency) but P/FCF is never computed
    d = compute_derived(QUARTERS, [], market_cap=600, idr_reporter=False)
    assert d["fcf_ttm"] == 60
    assert "price_to_fcf_ttm" not in d

    # nothing at all
    assert compute_derived([], [], None, True) == {}


async def test_ttm_tolerates_one_gap_and_ebit_fallback():
    # newest quarter has no cash-flow data yet (Yahoo lag) and no EBIT row,
    # only operating income — both must still produce TTM figures
    gapped = [
        {"revenue": 130, "operating_income": 13, "interest_expense": 2},
        {"revenue": 120, "ebit": 12, "interest_expense": 2,
         "operating_cash_flow": 20, "capital_expenditure": -5},
        {"revenue": 110, "ebit": 11, "interest_expense": 2,
         "operating_cash_flow": 20, "capital_expenditure": -5},
        {"revenue": 100, "ebit": 10, "interest_expense": 2,
         "operating_cash_flow": 20, "capital_expenditure": -5},
        {"revenue": 90, "ebit": 9, "interest_expense": 2,
         "operating_cash_flow": 20, "capital_expenditure": -5},
    ]
    d = compute_derived(gapped, [], market_cap=None, idr_reporter=True)
    # EBIT ttm = 13 (op income fallback) + 12 + 11 + 10 = 46 -> 46/8 = 5.75
    assert d["interest_coverage"] == pytest.approx(5.75)
    # OCF/capex ttm skip the gapped newest quarter: 4 x 20 - |4 x -5| = 60
    assert d["fcf_ttm"] == 60


async def _login(client, email):
    """Register, verify and sign in. See helpers.register_verified."""
    return await register_verified(client, email, "password-123")


async def _seed_statement_rows():
    from app.db import SessionLocal
    from app.models import FinancialStatement, PriceHistory, Security

    async with SessionLocal() as session:
        async with session.begin():
            sec = Security(
                ticker="STMT", yahoo_symbol="STMT.JK",
                name="Statement Uji Coba Tbk.", kind="stock",
            )
            session.add(sec)
            await session.flush()
            session.add(PriceHistory(
                security_id=sec.id, trade_date=date(2026, 7, 17), close=500,
            ))
            quarter_ends = [
                date(2026, 3, 31), date(2025, 12, 31),
                date(2025, 9, 30), date(2025, 6, 30),
            ]
            for period_end, items in zip(quarter_ends, QUARTERS):
                session.add(FinancialStatement(
                    security_id=sec.id, period_type="quarterly",
                    period_end=period_end, items=items,
                ))
            for year, items in ((2025, ANNUAL[0]), (2024, ANNUAL[1])):
                session.add(FinancialStatement(
                    security_id=sec.id, period_type="annual",
                    period_end=date(year, 12, 31), items=items,
                ))
    return sec.ticker


async def test_financials_endpoint(client):
    await _seed_statement_rows()
    auth = await _login(client, "stmt@example.com")

    r = await client.get("/securities/STMT/financials", headers=auth)
    assert r.status_code == 200
    body = r.json()

    # newest first, correctly split by period type
    assert [p["period_end"] for p in body["annual"]] == ["2025-12-31", "2024-12-31"]
    assert body["quarterly"][0]["period_end"] == "2026-03-31"
    assert body["quarterly"][0]["items"]["revenue"] == 130

    # derived metrics flow through (no fundamentals row -> IDR assumed,
    # but no market cap -> no P/FCF)
    assert body["currency"] is None
    assert body["derived"]["interest_coverage"] == pytest.approx(5.75)
    assert body["derived"]["piotroski_f"] == 8
    assert body["derived"]["price_to_fcf_ttm"] is None

    # unknown ticker -> 404
    assert (
        await client.get("/securities/XXXX/financials", headers=auth)
    ).status_code == 404


async def test_statements_sync_upserts(client, monkeypatch):
    import app.sync.statements as stmts

    payload = {
        ("annual", date(2025, 12, 31)): {"revenue": 500.0, "net_income": 50.0},
        ("quarterly", date(2026, 3, 31)): {"revenue": 140.0},
    }
    monkeypatch.setattr(stmts, "_fetch_statements", lambda sym: payload)

    result = await stmts.sync_statements(["STMT"])
    assert result.synced == 1 and result.periods == 2

    # idempotent: same periods upsert, no duplicates
    result = await stmts.sync_statements(["STMT"])
    assert result.synced == 1 and result.periods == 2

    from sqlalchemy import func, select

    from app.db import SessionLocal
    from app.models import FinancialStatement, Security

    async with SessionLocal() as session:
        sec_id = await session.scalar(
            select(Security.id).where(Security.ticker == "STMT")
        )
        count = await session.scalar(
            select(func.count())
            .select_from(FinancialStatement)
            .where(
                FinancialStatement.security_id == sec_id,
                FinancialStatement.period_type == "annual",
                FinancialStatement.period_end == date(2025, 12, 31),
            )
        )
        assert count == 1


async def test_statements_sync_isolates_failures(client, monkeypatch):
    import app.sync.statements as stmts

    def explode(sym: str):
        raise RuntimeError("Yahoo tantrum")

    monkeypatch.setattr(stmts, "_fetch_statements", explode)
    result = await stmts.sync_statements(["STMT"])
    assert result.synced == 0
    assert result.failed == ["STMT"]
