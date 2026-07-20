import logging
import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser, Session
from app.models import (
    CashFlow,
    Portfolio,
    PriceHistory,
    Security,
    Transaction,
    User,
)
from app.scheduler import enqueue_backfill
from app.schemas import (
    CashFlowIn,
    CashFlowOut,
    CashSummaryOut,
    HoldingOut,
    HoldingsOut,
    HoldingsTotals,
    PortfolioIn,
    PortfolioOut,
    PortfolioUpdate,
    TransactionIn,
    TransactionListOut,
    TransactionOut,
    TransactionUpdate,
)

router = APIRouter(tags=["portfolios"])
logger = logging.getLogger(__name__)

JAKARTA = ZoneInfo("Asia/Jakarta")
SHARES_PER_LOT = 100


async def _get_owned_portfolio(
    portfolio_id: uuid.UUID, user: User, session: AsyncSession
) -> Portfolio:
    portfolio = await session.scalar(
        select(Portfolio).where(
            Portfolio.id == portfolio_id, Portfolio.user_id == user.id
        )
    )
    if portfolio is None:
        # 404 for "not yours" too — never reveal that someone else's exists
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Portfolio not found")
    return portfolio


async def _cash_state(
    session: AsyncSession, portfolio_id: uuid.UUID
) -> tuple[int, bool]:
    """(balance, tracked). Balance = deposits - withdrawals - buy costs
    (incl. fees) + sell proceeds (net of fees).

    Only trades ON OR AFTER the first cash-flow date count: opting into
    the ledger mid-life must not let old buys drag the balance negative.
    Backdating the opening deposit before the first trade includes the
    full history (the demo seed does this). tracked=False means the
    portfolio never opted in (original, unblocked behavior)."""
    row = (
        await session.execute(
            sa_text(
                """
                SELECT
                  COALESCE((SELECT SUM(CASE WHEN cf.type = 'DEPOSIT'
                                            THEN cf.amount ELSE -cf.amount END)
                            FROM cash_flows cf
                            WHERE cf.portfolio_id = :p), 0)
                  +
                  COALESCE((SELECT SUM(CASE WHEN t.type = 'BUY'
                                            THEN -(t.shares * t.price_per_share + t.fee)
                                            ELSE t.shares * t.price_per_share - t.fee END)
                            FROM transactions t
                            WHERE t.portfolio_id = :p
                              AND t.executed_at >= (SELECT MIN(cf3.occurred_at)
                                                    FROM cash_flows cf3
                                                    WHERE cf3.portfolio_id = :p)), 0)
                  AS balance,
                  EXISTS(SELECT 1 FROM cash_flows cf2
                         WHERE cf2.portfolio_id = :p) AS tracked
                """
            ),
            {"p": portfolio_id},
        )
    ).one()
    return int(row.balance), bool(row.tracked)


def _txn_out(txn: Transaction, ticker: str) -> TransactionOut:
    return TransactionOut(
        id=txn.id,
        ticker=ticker,
        type=txn.type,
        lots=txn.shares // SHARES_PER_LOT,
        shares=txn.shares,
        price_per_share=txn.price_per_share,
        fee=txn.fee,
        executed_at=txn.executed_at,
        note=txn.note,
        created_at=txn.created_at,
    )


# ---------------------------------------------------------------------------
# Portfolio CRUD
# ---------------------------------------------------------------------------

@router.post("/portfolios", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    payload: PortfolioIn, user: CurrentUser, session: Session
) -> Portfolio:
    portfolio = Portfolio(
        user_id=user.id, name=payload.name, description=payload.description
    )
    session.add(portfolio)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already have a portfolio with this name"
        )
    await session.refresh(portfolio)
    return portfolio


@router.get("/portfolios", response_model=list[PortfolioOut])
async def list_portfolios(user: CurrentUser, session: Session) -> list[Portfolio]:
    result = await session.scalars(
        select(Portfolio)
        .where(Portfolio.user_id == user.id)
        .order_by(Portfolio.created_at)
    )
    return list(result)


@router.get("/portfolios/{portfolio_id}", response_model=PortfolioOut)
async def get_portfolio(
    portfolio_id: uuid.UUID, user: CurrentUser, session: Session
) -> Portfolio:
    return await _get_owned_portfolio(portfolio_id, user, session)


@router.patch("/portfolios/{portfolio_id}", response_model=PortfolioOut)
async def update_portfolio(
    portfolio_id: uuid.UUID,
    payload: PortfolioUpdate,
    user: CurrentUser,
    session: Session,
) -> Portfolio:
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)
    if payload.name is not None:
        portfolio.name = payload.name
    if payload.description is not None:
        portfolio.description = payload.description
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already have a portfolio with this name"
        )
    await session.refresh(portfolio)
    return portfolio


@router.delete("/portfolios/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: uuid.UUID, user: CurrentUser, session: Session
) -> None:
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)
    await session.delete(portfolio)  # transactions cascade via FK
    await session.commit()


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@router.post(
    "/portfolios/{portfolio_id}/transactions",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_transaction(
    portfolio_id: uuid.UUID,
    payload: TransactionIn,
    user: CurrentUser,
    session: Session,
) -> TransactionOut:
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)

    security = await session.scalar(
        select(Security).where(Security.ticker == payload.ticker.upper())
    )
    if security is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Unknown ticker {payload.ticker.upper()!r} — not in the IDX universe",
        )
    if security.kind != "stock":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"{security.ticker} is an index, not a tradable stock",
        )

    if payload.executed_at > datetime.now(JAKARTA).date():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "executed_at cannot be in the future"
        )

    shares = payload.lots * SHARES_PER_LOT

    if payload.type == "BUY":
        # Portfolios that opted into the cash ledger cannot spend cash
        # they don't have. Untracked portfolios keep the original behavior.
        balance, tracked = await _cash_state(session, portfolio.id)
        cost = shares * payload.price_per_share + payload.fee
        if tracked and cost > balance:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Insufficient cash: this buy costs Rp {cost:,} but only "
                f"Rp {balance:,} is available. Deposit more or reduce the order.",
            )

    if payload.type == "SELL":
        held = (
            await session.scalar(
                sa_text(
                    "SELECT shares FROM holdings"
                    " WHERE portfolio_id = :p AND security_id = :s"
                ),
                {"p": portfolio.id, "s": security.id},
            )
            or 0
        )
        if shares > held:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Cannot sell {payload.lots} lots of {security.ticker}; "
                f"only {held // SHARES_PER_LOT} held",
            )

    txn = Transaction(
        portfolio_id=portfolio.id,
        security_id=security.id,
        type=payload.type,
        shares=shares,
        price_per_share=payload.price_per_share,
        fee=payload.fee,
        executed_at=payload.executed_at,
        note=payload.note,
    )
    session.add(txn)
    await session.commit()
    await session.refresh(txn)

    # First time anyone touches this ticker -> lazy 5y price backfill (Step 3)
    has_history = await session.scalar(
        select(PriceHistory.security_id)
        .where(PriceHistory.security_id == security.id)
        .limit(1)
    )
    if has_history is None:
        try:
            enqueue_backfill(security.ticker)
            logger.info("enqueued first-use price backfill for %s", security.ticker)
        except RuntimeError:
            logger.error(
                "scheduler unavailable — price backfill for %s NOT enqueued; "
                "run: python -m app.sync backfill --ticker %s",
                security.ticker, security.ticker,
            )

    return _txn_out(txn, security.ticker)


@router.get(
    "/portfolios/{portfolio_id}/transactions", response_model=TransactionListOut
)
async def list_transactions(
    portfolio_id: uuid.UUID,
    user: CurrentUser,
    session: Session,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TransactionListOut:
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)

    total = await session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.portfolio_id == portfolio.id)
    )
    rows = await session.execute(
        select(Transaction, Security.ticker)
        .join(Security, Security.id == Transaction.security_id)
        .where(Transaction.portfolio_id == portfolio.id)
        .order_by(Transaction.executed_at.desc(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return TransactionListOut(
        items=[_txn_out(txn, ticker) for txn, ticker in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/portfolios/{portfolio_id}/transactions/{transaction_id}",
    response_model=TransactionOut,
)
async def update_transaction(
    portfolio_id: uuid.UUID,
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
    user: CurrentUser,
    session: Session,
) -> TransactionOut:
    """Edit an existing transaction. The security is fixed; everything else
    may change. The edit is applied, then the derived state is re-validated
    (holdings never net-negative, cash never negative when tracked) and
    rolled back if it would break either invariant."""
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)
    txn = await session.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.portfolio_id == portfolio.id,
        )
    )
    if txn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")

    if payload.executed_at > datetime.now(JAKARTA).date():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "executed_at cannot be in the future"
        )

    security = await session.get(Security, txn.security_id)
    ticker = security.ticker  # capture before rollback can expire it

    txn.type = payload.type
    txn.shares = payload.lots * SHARES_PER_LOT
    txn.price_per_share = payload.price_per_share
    txn.fee = payload.fee
    txn.executed_at = payload.executed_at
    txn.note = payload.note
    await session.flush()

    net = await session.scalar(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.type == "BUY", Transaction.shares),
                        else_=-Transaction.shares,
                    )
                ),
                0,
            )
        ).where(
            Transaction.portfolio_id == portfolio.id,
            Transaction.security_id == txn.security_id,
        )
    )
    if net < 0:
        await session.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"This edit would leave {ticker} holdings at "
            f"{net // SHARES_PER_LOT} lots. Adjust the sells for this ticker first.",
        )

    balance, tracked = await _cash_state(session, portfolio.id)
    if tracked and balance < 0:
        await session.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"This edit would overspend cash by Rp {abs(balance):,}. "
            "Deposit more or reduce the order.",
        )

    await session.commit()
    await session.refresh(txn)
    return _txn_out(txn, ticker)


@router.delete(
    "/portfolios/{portfolio_id}/transactions/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_transaction(
    portfolio_id: uuid.UUID,
    transaction_id: uuid.UUID,
    user: CurrentUser,
    session: Session,
) -> None:
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)
    txn = await session.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.portfolio_id == portfolio.id,
        )
    )
    if txn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")

    if txn.type == "BUY":
        # Deleting a buy must not leave past sells exceeding total buys
        net_without = await session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (Transaction.type == "BUY", Transaction.shares),
                            else_=-Transaction.shares,
                        )
                    ),
                    0,
                )
            ).where(
                Transaction.portfolio_id == portfolio.id,
                Transaction.security_id == txn.security_id,
                Transaction.id != txn.id,
            )
        )
        if net_without < 0:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Deleting this buy would leave sells exceeding buys for the ticker",
            )

    await session.delete(txn)
    await session.commit()


# ---------------------------------------------------------------------------
# Cash ledger
# ---------------------------------------------------------------------------

@router.get("/portfolios/{portfolio_id}/cash", response_model=CashSummaryOut)
async def get_cash(
    portfolio_id: uuid.UUID, user: CurrentUser, session: Session
) -> CashSummaryOut:
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)
    balance, tracked = await _cash_state(session, portfolio.id)
    flows = list(
        await session.scalars(
            select(CashFlow)
            .where(CashFlow.portfolio_id == portfolio.id)
            .order_by(CashFlow.occurred_at.desc(), CashFlow.created_at.desc())
            .limit(20)
        )
    )
    return CashSummaryOut(
        balance=balance,
        tracked=tracked,
        flows=[CashFlowOut.model_validate(f) for f in flows],
    )


@router.post(
    "/portfolios/{portfolio_id}/cash",
    response_model=CashSummaryOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_cash_flow(
    portfolio_id: uuid.UUID,
    payload: CashFlowIn,
    user: CurrentUser,
    session: Session,
) -> CashSummaryOut:
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)
    occurred = payload.occurred_at or datetime.now(JAKARTA).date()
    if occurred > datetime.now(JAKARTA).date():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "occurred_at cannot be in the future"
        )

    if payload.type == "WITHDRAW":
        balance, _ = await _cash_state(session, portfolio.id)
        if payload.amount > balance:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Cannot withdraw Rp {payload.amount:,}; only Rp {balance:,} available",
            )

    session.add(
        CashFlow(
            portfolio_id=portfolio.id,
            type=payload.type,
            amount=payload.amount,
            occurred_at=occurred,
            note=payload.note,
        )
    )
    await session.commit()
    return await get_cash(portfolio_id, user, session)


@router.delete(
    "/portfolios/{portfolio_id}/cash/{flow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_cash_flow(
    portfolio_id: uuid.UUID,
    flow_id: uuid.UUID,
    user: CurrentUser,
    session: Session,
) -> None:
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)
    flow = await session.scalar(
        select(CashFlow).where(
            CashFlow.id == flow_id, CashFlow.portfolio_id == portfolio.id
        )
    )
    if flow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cash flow not found")

    # Recompute the balance as if the flow were gone (this also handles the
    # earliest-deposit case, where the ledger start date itself moves).
    # Deleting the last remaining flow turns tracking off entirely — that
    # is the supported way to opt back out of the cash ledger.
    await session.delete(flow)
    await session.flush()
    balance, tracked = await _cash_state(session, portfolio.id)
    if tracked and balance < 0:
        await session.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Deleting this entry would leave the cash balance at "
            f"Rp {balance:,}. Remove the spending that relied on it first.",
        )
    await session.commit()


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------

@router.get("/portfolios/{portfolio_id}/holdings", response_model=HoldingsOut)
async def get_holdings(
    portfolio_id: uuid.UUID, user: CurrentUser, session: Session
) -> HoldingsOut:
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)

    # Price preference: delayed quote, else the most recent stored close
    # (as_of stays NULL then — the row is priced "at last close", and the
    # UI labels it that way instead of faking a quote timestamp).
    rows = await session.execute(
        sa_text(
            """
            SELECT s.ticker, s.name, h.shares, h.avg_cost_per_share,
                   COALESCE(q.price, ph.close) AS last_price,
                   q.as_of,
                   ph.trade_date AS last_close_date
            FROM holdings h
            JOIN securities s ON s.id = h.security_id
            LEFT JOIN latest_quotes q ON q.security_id = h.security_id
            LEFT JOIN LATERAL (
                SELECT close, trade_date FROM price_history p
                WHERE p.security_id = h.security_id
                ORDER BY p.trade_date DESC LIMIT 1
            ) ph ON TRUE
            WHERE h.portfolio_id = :pid
            ORDER BY s.ticker
            """
        ),
        {"pid": portfolio.id},
    )

    holdings: list[HoldingOut] = []
    total_cost = 0
    total_mv = 0
    total_pnl = 0
    unpriced = 0

    for r in rows.mappings():
        shares = int(r["shares"])
        avg_cost = Decimal(r["avg_cost_per_share"])
        cost_basis = int(
            (avg_cost * shares).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        )
        last_price = r["last_price"]

        if last_price is None:
            market_value = pnl = pnl_pct = None
            unpriced += 1
        else:
            market_value = shares * int(last_price)
            pnl = market_value - cost_basis
            pnl_pct = (
                round(pnl / cost_basis * 100, 2) if cost_basis else None
            )
            total_mv += market_value
            total_pnl += pnl

        total_cost += cost_basis
        holdings.append(
            HoldingOut(
                ticker=r["ticker"],
                name=r["name"],
                shares=shares,
                lots=shares // SHARES_PER_LOT,
                avg_cost_per_share=float(round(avg_cost, 2)),
                cost_basis=cost_basis,
                last_price=last_price,
                market_value=market_value,
                unrealized_pnl=pnl,
                unrealized_pnl_pct=pnl_pct,
                as_of=r["as_of"],
                last_close_date=r["last_close_date"],
            )
        )

    priced_any = len(holdings) > unpriced
    cash_balance, cash_tracked = await _cash_state(session, portfolio.id)
    return HoldingsOut(
        portfolio_id=portfolio.id,
        holdings=holdings,
        totals=HoldingsTotals(
            cost_basis=total_cost,
            market_value=total_mv if priced_any else None,
            unrealized_pnl=total_pnl if priced_any else None,
            unpriced_holdings=unpriced,
            cash_balance=cash_balance,
            cash_tracked=cash_tracked,
        ),
    )
