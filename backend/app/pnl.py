"""Realized P&L via the average-cost method.

Pure and unit-tested. Matches the `holdings` view's cost-basis convention:
buy fees are part of cost basis, sell fees reduce proceeds. A sell realizes
proceeds minus the average cost of the shares sold; the running cost basis
is reduced proportionally so later sells use the updated average.

Whole-rupiah in, whole-rupiah out. Rounding is applied to each sell's
cost-of-shares-sold so the figure stays integer-honest.
"""

from collections.abc import Iterable


def realized_pnl(trades: Iterable[tuple[str, int, int, int]]) -> int:
    """Realized P&L for ONE security, from its trades in chronological order.

    Each trade is (type, shares, price_per_share, fee) with type in
    {"BUY", "SELL"}. Returns whole rupiah (can be negative).
    """
    shares = 0
    cost = 0  # cost basis of the shares currently held
    realized = 0

    for kind, qty, price, fee in trades:
        if kind == "BUY":
            cost += qty * price + fee
            shares += qty
        else:  # SELL
            proceeds = qty * price - fee
            if shares <= 0:
                # No basis to net against (oversell is blocked upstream, so
                # this is defensive) — the whole proceeds are realized.
                realized += proceeds
                continue
            avg = cost / shares
            basis_sold = round(avg * min(qty, shares))
            realized += proceeds - basis_sold
            cost -= basis_sold
            shares -= qty
            if shares <= 0:
                shares = 0
                cost = 0  # guard against float drift on a full exit

    return realized
