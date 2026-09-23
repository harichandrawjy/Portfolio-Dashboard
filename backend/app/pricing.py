"""The one rule for "what is this stock's price right now".

A delayed quote is trusted only while it is strictly NEWER than the last
published bar; otherwise the most recent stored close wins.

Why this needs to be one function rather than a habit: `latest_quotes` is
refreshed only for tickers someone HOLDS, while `price_history` is refreshed
for anything with history. Sell your last share and the quote freezes on that
day while the bars keep arriving. `COALESCE(q.price, ph.close)` — the obvious
way to write it, and what five queries once said — prefers the frozen quote
forever.

It was fixed once in the holdings table (after a sell-then-cancel left PACK at
a six-day-old 466 against a 560 close) and on the stock page, and survived in
search, the allocation donut and the position panel. Search then offered ESSA
at 715 — the quote from the day it was sold — against a 610 close, and the
buy form pre-filled that price. Every copy was a place to forget.

Strictly greater, not >=: between the 18:30 bar job and the next morning's
first quote, the two share a date, and the settled close is the better number.

These build SQL from ALIAS NAMES chosen by the calling query — trusted
literals written in this codebase, never user input — so the f-string is not
an injection surface. Each caller's lateral subquery must select `trade_date`
alongside `close`.
"""


def quote_is_fresh(q: str, ph: str) -> str:
    """SQL condition: the quote aliased `q` should be used over the bar `ph`.

    Two cases, and the first is easy to lose:

    - **No bars at all** — a ticker bought before its backfill has landed. Any
      quote beats no price, dated or not (`QuoteSnapshot.trade_date` is
      nullable, so undated quotes do reach the table). Requiring a date here
      turned a priced holding into an unpriced one, which zeroed it out of the
      allocation donut. The stock page already behaved this way via
      `last_close ?? quote_price`; this makes the SQL agree.
    - **Bars exist** — the quote must be dated AND strictly newer, or it is a
      frozen leftover and the settled close wins.
    """
    return (
        f"({q}.price IS NOT NULL AND ({ph}.trade_date IS NULL "
        f"OR ({q}.trade_date IS NOT NULL AND {q}.trade_date > {ph}.trade_date)))"
    )


def fresh_price(q: str, ph: str) -> str:
    """SQL expression: the current price under the rule above."""
    return f"CASE WHEN {quote_is_fresh(q, ph)} THEN {q}.price ELSE {ph}.close END"
