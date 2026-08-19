import { MagnifyingGlass, Minus, Plus } from "@phosphor-icons/react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import {
  api,
  type Holding,
  type Holdings,
  type NewTransaction,
  type SearchResult,
  type TxnType,
} from "../api/client";
import { useDebounced } from "../lib/hooks";
import {
  digitsOnly,
  fmtDateShort,
  fmtNum,
  fmtRp,
  groupDigits,
} from "../lib/format";
import { BinaryToggle, Button, ErrorNote, Field, Modal, useToast } from "./ui";

const SHARES_PER_LOT = 100;

// Typical Indonesian retail broker fees (e.g. Stockbit): buys 0.15%,
// sells 0.25% (the extra 0.1% is sales tax). The ledger still stores the
// computed whole-rupiah fee — the percent is an entry convenience.
const DEFAULT_BUY_FEE_PCT = "0.15";
const DEFAULT_SELL_FEE_PCT = "0.25";

const todayISO = () => new Date().toISOString().slice(0, 10);

/** IDX price tick sizes by price band. */
function tickFor(price: number): number {
  if (price < 200) return 1;
  if (price < 500) return 2;
  if (price < 2000) return 5;
  if (price < 5000) return 10;
  return 25;
}

/** One dropdown row, whether it came from universe search (BUY) or the
 *  portfolio's own holdings (SELL). */
interface Suggestion {
  ticker: string;
  name: string;
  last_price: number | null;
  heldLots: number | null;
  sector: string | null;
}

function Stepper({
  label,
  value,
  onChange,
  step,
  min = 1,
  hint,
  grouped = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  step: (current: number, dir: 1 | -1) => number;
  min?: number;
  hint?: string | null;
  /** render with id-ID thousands dots; onChange still emits raw digits */
  grouped?: boolean;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const num = parseInt(value, 10);
  const current = Number.isFinite(num) ? num : 0;
  const bump = (dir: 1 | -1) =>
    onChange(String(Math.max(min, step(current, dir))));
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="w-wide text-[11px] font-bold uppercase tracking-[0.12em] text-ink-2">
        {label}
      </label>
      {/* The ring belongs to the group: drawn on the input it would be clipped
          by this container's overflow-hidden, leaving focus invisible. */}
      <div className="flex items-stretch overflow-hidden bg-panel-2 ring-1 ring-transparent focus-within:bg-panel focus-within:ring-2 focus-within:ring-accent">
        <button
          type="button" onClick={() => bump(-1)}
          aria-label={`Decrease ${label}`}
          className="px-3 text-ink-2 outline-none transition-colors hover:bg-panel-2 focus-visible:bg-panel-3 focus-visible:text-ink"
        >
          <Minus size={13} weight="bold" />
        </button>
        <input
          id={id}
          inputMode="numeric" aria-describedby={hint ? hintId : undefined}
          value={grouped ? groupDigits(value) : value}
          onChange={(e) =>
            onChange(grouped ? digitsOnly(e.target.value) : e.target.value)
          }
          className="w-full border-x border-line bg-transparent py-2 text-center text-[13px] text-ink outline-none"
        />
        <button
          type="button" onClick={() => bump(1)}
          aria-label={`Increase ${label}`}
          className="px-3 text-ink-2 outline-none transition-colors hover:bg-panel-2 focus-visible:bg-panel-3 focus-visible:text-ink"
        >
          <Plus size={13} weight="bold" />
        </button>
      </div>
      {hint && (
        <span id={hintId} className="text-xs text-ink-3">
          {hint}
        </span>
      )}
    </div>
  );
}

export function AddTransactionModal({
  portfolioId,
  onClose,
  onSaved,
  initialTicker,
  initialType,
}: {
  portfolioId: string;
  onClose: () => void;
  onSaved: () => void;
  initialTicker?: string;
  initialType?: TxnType;
}) {
  const [type, setType] = useState<TxnType>(initialType ?? "BUY");
  const [ticker, setTicker] = useState(initialTicker ?? "");
  const [tickerPicked, setTickerPicked] = useState(!!initialTicker);
  const [lots, setLots] = useState("1");
  const [price, setPrice] = useState("");
  const [priceAutofilled, setPriceAutofilled] = useState(false);
  const [priceHint, setPriceHint] = useState<string | null>(null);
  const userTypedPrice = useRef(false);
  const pollToken = useRef(0);
  const [feePct, setFeePct] = useState(DEFAULT_BUY_FEE_PCT);
  const feePctTouched = useRef(false);
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  // ---- holdings + cash (sellable things & buying power) ------------
  const [portfolioState, setPortfolioState] = useState<Holdings | null>(null);
  // A failed lookup is not the same as an empty wallet — keep them apart so a
  // network blip cannot masquerade as "this portfolio has no cash".
  const [stateError, setStateError] = useState<string | null>(null);
  useEffect(() => {
    api.holdings(portfolioId).then(
      (h) => {
        setPortfolioState(h);
        setStateError(null);
      },
      (e: Error) => {
        setPortfolioState(null);
        setStateError(e.message);
      },
    );
  }, [portfolioId]);
  const held: Holding[] | null = portfolioState?.holdings ?? null;
  const cashTracked = portfolioState?.totals.cash_tracked ?? false;
  const cashBalance = portfolioState?.totals.cash_balance ?? 0;

  // ---- autocomplete ------------------------------------------------
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const debouncedQuery = useDebounced(ticker, 250);
  const boxRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const listId = useId();

  // BUY: universe search on the backend
  useEffect(() => {
    if (type === "SELL" || tickerPicked || debouncedQuery.trim().length < 1) {
      setSearchResults([]);
      return;
    }
    let cancelled = false;
    api.searchSecurities(debouncedQuery.trim()).then(
      (r) => {
        if (!cancelled) {
          setSearchResults(r);
          setOpen(true);
        }
      },
      () => {
        if (!cancelled) setSearchResults([]);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery, tickerPicked, type]);

  // SELL: filter the holdings client-side; empty query lists everything
  const suggestions: Suggestion[] = useMemo(() => {
    if (type === "SELL") {
      const q = ticker.trim().toUpperCase();
      return (held ?? [])
        .filter(
          (h) =>
            !q || h.ticker.startsWith(q) || h.name.toUpperCase().includes(q),
        )
        .map((h) => ({
          ticker: h.ticker,
          name: h.name,
          last_price: h.last_price,
          heldLots: h.lots,
          sector: null,
        }));
    }
    return searchResults.map((r) => ({
      ticker: r.ticker,
      name: r.name,
      last_price: r.last_price,
      heldLots: null,
      sector: r.sector,
    }));
  }, [type, ticker, held, searchResults]);

  useEffect(() => {
    setOpen(false);
    setSearchResults([]);
    // follow the broker default until the user sets their own rate
    if (!feePctTouched.current)
      setFeePct(type === "BUY" ? DEFAULT_BUY_FEE_PCT : DEFAULT_SELL_FEE_PCT);
  }, [type]);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node))
        setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, []);

  useEffect(() => {
    return () => {
      pollToken.current += 1;
    };
  }, []);

  // Pre-set ticker (row Buy/Sell buttons): prefill the price from search.
  useEffect(() => {
    if (!initialTicker) return;
    let cancelled = false;
    api.searchSecurities(initialTicker).then(
      (rs) => {
        if (cancelled) return;
        const hit = rs.find((r) => r.ticker === initialTicker);
        if (hit?.last_price != null && !userTypedPrice.current) {
          setPrice(String(hit.last_price));
          setPriceAutofilled(true);
          setPriceHint("Last known price · edit freely");
        }
      },
      () => {},
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Back-dating a trade should price it at that day's close, not today's.
  // Today keeps using the live quote, which is fresher than the last bar.
  useEffect(() => {
    const symbol = ticker.trim().toUpperCase();
    if (!tickerPicked || !symbol) return;
    if (date >= todayISO()) return; // today -> quote-based prefill stands
    if (userTypedPrice.current) return; // never overwrite a typed price

    let cancelled = false;
    api.securityCloseOn(symbol, date).then(
      (r) => {
        if (cancelled || userTypedPrice.current) return;
        if (r.close == null) {
          setPriceHint("No close stored for that date · enter the price");
          return;
        }
        setPrice(String(r.close));
        setPriceAutofilled(true);
        setPriceHint(
          r.trade_date === date
            ? `Close on ${fmtDateShort(r.trade_date)} · edit freely`
            : `No trading on ${fmtDateShort(date)}; close on ${fmtDateShort(r.trade_date!)} · edit freely`,
        );
      },
      () => {},
    );
    return () => {
      cancelled = true;
    };
  }, [ticker, tickerPicked, date]);

  /** BUY of a never-priced ticker: enqueue the lazy backfill and poll. */
  const fetchPriceInBackground = async (symbol: string) => {
    const token = ++pollToken.current;
    setPriceHint("No local price yet · fetching…");
    try {
      const res = await api.ensurePrices(symbol);
      if (res.status === "unavailable") {
        if (pollToken.current === token)
          setPriceHint("Price service unavailable · enter the price manually");
        return;
      }
      for (let attempt = 0; attempt < 8; attempt++) {
        await new Promise((r) => setTimeout(r, 1500));
        if (pollToken.current !== token) return;
        const hits = await api.searchSecurities(symbol);
        const hit = hits.find((h) => h.ticker === symbol);
        if (hit?.last_price != null) {
          if (pollToken.current !== token) return;
          if (!userTypedPrice.current) {
            setPrice(String(hit.last_price));
            setPriceAutofilled(true);
            setPriceHint("Last known price · edit freely");
          } else {
            setPriceHint(null);
          }
          return;
        }
      }
      if (pollToken.current === token)
        setPriceHint("No price available for this ticker yet");
    } catch {
      if (pollToken.current === token) setPriceHint(null);
    }
  };

  // Keep the highlighted option in view as the arrow keys walk the list.
  useEffect(() => {
    if (activeIdx < 0 || !listRef.current) return;
    listRef.current
      .querySelector<HTMLElement>(`[data-idx="${activeIdx}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [activeIdx]);

  const onPriceEdit = (v: string) => {
    setPrice(v);
    setPriceAutofilled(false);
    setPriceHint(null);
    userTypedPrice.current = true;
  };

  /** Arrow keys walk the list, Enter takes the highlight, Escape closes the
   *  list before the dialog — without this the ticker step is mouse-only. */
  const onTickerKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      if (suggestions.length === 0) return;
      const dir = e.key === "ArrowDown" ? 1 : -1;
      setActiveIdx((i) => (i + dir + suggestions.length) % suggestions.length);
      return;
    }
    if (e.key === "Enter" && open && suggestions[activeIdx]) {
      e.preventDefault();
      pickSuggestion(suggestions[activeIdx]);
      return;
    }
    if (e.key === "Escape" && open) {
      // keep Escape local to the list; the dialog owns it once this is closed
      e.stopPropagation();
      e.nativeEvent.stopImmediatePropagation();
      setOpen(false);
      setActiveIdx(-1);
    }
  };

  const pickSuggestion = (s: Suggestion) => {
    setTicker(s.ticker);
    setTickerPicked(true);
    setOpen(false);
    pollToken.current += 1;
    if (price === "" || priceAutofilled) userTypedPrice.current = false;
    if (s.last_price != null) {
      if (price === "" || priceAutofilled) {
        setPrice(String(s.last_price));
        setPriceAutofilled(true);
        setPriceHint("Last known price · edit freely");
      }
    } else if (type === "BUY") {
      void fetchPriceInBackground(s.ticker);
    }
    // selling: clamp the lot count to what is actually held
    if (s.heldLots != null) {
      const cur = parseInt(lots, 10);
      if (!Number.isFinite(cur) || cur < 1 || cur > s.heldLots)
        setLots(String(Math.max(1, Math.min(cur || 1, s.heldLots))));
    }
  };

  // ---- derived order math ------------------------------------------
  const lotsNum = parseInt(lots, 10);
  const lotsOk = Number.isFinite(lotsNum) && lotsNum >= 1;
  const priceNum = parseInt(price, 10);
  const priceOk = Number.isFinite(priceNum) && priceNum >= 1;
  // accept both "0.15" and "0,15"
  const feeRate = parseFloat(feePct.replace(",", ".")) / 100;
  const feeOk = Number.isFinite(feeRate) && feeRate >= 0 && feeRate <= 0.1;
  const shares = lotsOk ? lotsNum * SHARES_PER_LOT : null;
  const baseValue =
    priceOk && lotsOk ? lotsNum * SHARES_PER_LOT * priceNum : null;
  const feeRp =
    baseValue != null && feeOk ? Math.round(baseValue * feeRate) : null;

  const heldPosition = held?.find(
    (h) => h.ticker === ticker.trim().toUpperCase(),
  );
  const sellingUnheld =
    type === "SELL" &&
    held !== null &&
    ticker.trim() !== "" &&
    tickerPicked &&
    !heldPosition;

  const buyMaxLots =
    type === "BUY" && priceOk && stateError === null
      ? Math.max(
          0,
          Math.floor(
            cashBalance /
              (priceNum * SHARES_PER_LOT * (1 + (feeOk ? feeRate : 0))),
          ),
        )
      : null;
  const sellMaxLots = type === "SELL" && heldPosition ? heldPosition.lots : null;
  const sliderMax = type === "BUY" ? buyMaxLots : sellMaxLots;

  const total =
    baseValue != null
      ? baseValue + (type === "BUY" ? (feeRp ?? 0) : -(feeRp ?? 0))
      : null;
  // Unknown buying power must not block the order; the server revalidates.
  const insufficient =
    type === "BUY" && stateError === null && total != null && total > cashBalance;

  const lotsHint =
    type === "SELL" && heldPosition
      ? `= ${fmtNum(shares)} shares · you hold ${fmtNum(heldPosition.lots)} lots`
      : shares != null
        ? `= ${fmtNum(shares)} shares`
        : "1 lot = 100 shares";

  const submit = async () => {
    setError(null);
    if (!ticker.trim()) return setError("Pick a ticker first.");
    if (!lotsOk) return setError("Lots must be a whole number of at least 1.");
    if (!priceOk)
      return setError("Price per share must be a positive whole-rupiah amount.");
    if (!feeOk)
      return setError("Fee percent must be between 0 and 10.");

    const txn: NewTransaction = {
      ticker: ticker.trim().toUpperCase(),
      type,
      lots: lotsNum,
      price_per_share: priceNum,
      fee: feeRp ?? 0,
      executed_at: date,
      note: note.trim() || null,
    };
    setBusy(true);
    try {
      await api.addTransaction(portfolioId, txn);
      onSaved();
      toast(
        `${type === "BUY" ? "Bought" : "Sold"} ${fmtNum(lotsNum)} lot${
          lotsNum > 1 ? "s" : ""
        } of ${txn.ticker} at ${fmtRp(priceNum)}.`,
      );
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Add transaction" onClose={onClose} wide>
      <div className="flex flex-col gap-4">
        {/* Side and ticker are one decision, read left to right. The ticker
            takes the wider track — company names need the room. */}
        <div className="grid gap-4 sm:grid-cols-[13rem_minmax(0,1fr)]">
          <div className="flex flex-col gap-2">
            <span className="w-wide text-[11px] font-bold uppercase tracking-[0.12em] text-ink-2">Side</span>
            {/* the broker convention, and the one place this system spends
                green/red on something unsigned — recording a sell as a buy
                is the expensive mistake this control exists to prevent */}
            <BinaryToggle
              label="Side" value={type}
              onChange={setType}
              options={[
                { value: "BUY", label: "Buy", tone: "pos" },
                { value: "SELL", label: "Sell", tone: "neg" },
              ]}
            />
          </div>

          {/* Ticker: universe search when buying, own holdings when selling */}
          <div ref={boxRef} className="relative">
            <label className="flex flex-col gap-2">
              <span className="w-wide text-[11px] font-bold uppercase tracking-[0.12em] text-ink-2">
                {type === "SELL" ? "Ticker (from this portfolio)" : "Ticker"}
              </span>
              <div className="relative">
                <MagnifyingGlass
                  size={15}
                  weight="light" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3"
                />
                <input
                  value={ticker}
                  onChange={(e) => {
                    setTicker(e.target.value.toUpperCase());
                    setTickerPicked(false);
                    setActiveIdx(-1);
                    if (type === "SELL") setOpen(true);
                  }}
                  onFocus={() => {
                    if (type === "SELL" || suggestions.length > 0) setOpen(true);
                  }}
                  onKeyDown={onTickerKeyDown}
                  placeholder={
                    type === "SELL"
                      ? "Pick a holding to sell"
                      : "BBCA, TLKM, or a company name"
                  }
                  autoFocus
                  role="combobox" aria-expanded={open}
                  aria-controls={listId}
                  aria-autocomplete="list" aria-activedescendant={
                    open && activeIdx >= 0 ? `${listId}-${activeIdx}` : undefined
                  }
                  className="w-full bg-panel-2 py-2.5 pl-9 pr-3 text-[13px] text-ink ring-1 ring-transparent placeholder:text-ink-3 outline-none transition-shadow focus:bg-panel focus:ring-2 focus:ring-accent"
                />
              </div>
              {sellingUnheld && (
                <span className="text-xs text-warn">
                  {ticker.trim().toUpperCase()} is not held in this portfolio.
                </span>
              )}
            </label>

            {open && (
              <ul
                ref={listRef}
                id={listId}
                role="listbox" aria-label="Ticker suggestions" className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto bg-panel py-1 ring-1 ring-ink"
              >
                {type === "SELL" && held !== null && held.length === 0 ? (
                  <li className="px-3 py-2 text-[13px] text-ink-3">
                    Nothing held in this portfolio yet.
                  </li>
                ) : suggestions.length === 0 ? (
                  type === "SELL" && (
                    <li className="px-3 py-2 text-[13px] text-ink-3">
                      No holding matches "{ticker.trim()}".
                    </li>
                  )
                ) : (
                  suggestions.map((s, i) => (
                    <li
                      key={s.ticker}
                      id={`${listId}-${i}`}
                      data-idx={i}
                      role="option" aria-selected={i === activeIdx}
                    >
                      <button
                        type="button" tabIndex={-1}
                        onMouseEnter={() => setActiveIdx(i)}
                        onClick={() => pickSuggestion(s)}
                        className={`flex w-full items-baseline gap-3 px-3 py-2 text-left transition-colors ${
                          i === activeIdx ? "bg-panel-2" : ""
                        }`}
                      >
                        <span className="text-[13px] font-semibold text-ink">
                          {s.ticker}
                        </span>
                        <span className="truncate text-xs text-ink-3">
                          {s.name}
                        </span>
                        <span className="ml-auto shrink-0">
                          {s.heldLots != null ? (
                            <span className="tnum text-xs text-ink-2">
                              {fmtNum(s.heldLots)} lots
                            </span>
                          ) : s.last_price != null ? (
                            <span className="tnum text-xs text-ink-2">
                              {fmtRp(s.last_price)}
                            </span>
                          ) : (
                            <span className="text-[11px] text-ink-3">
                              {s.sector ?? ""}
                            </span>
                          )}
                        </span>
                      </button>
                    </li>
                  ))
                )}
              </ul>
            )}
          </div>
        </div>

        {/* buying power strip — a buy always spends cash */}
        {type === "BUY" && stateError !== null && (
          <p className="bg-warn/10 px-3 py-2 text-xs text-warn ring-1 ring-warn/25">
            Couldn't check this portfolio's cash balance. You can still record
            the trade; the server validates it against the ledger.
          </p>
        )}
        {type === "BUY" && portfolioState !== null && (
          <div className="flex items-baseline justify-between bg-panel-2 px-3 py-2">
            <span className="text-[13px] text-ink-2">Cash available</span>
            <span
              className={`tnum text-[13px] font-semibold ${cashBalance > 0 ? "text-ink" : "text-neg"}`}
            >
              {fmtRp(cashBalance)}
            </span>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <Stepper
            label="Price per share (Rp)" value={price}
            onChange={onPriceEdit}
            step={(cur, dir) =>
              dir > 0 ? cur + tickFor(cur) : cur - tickFor(Math.max(0, cur - 1))
            }
            min={1}
            hint={priceHint}
            grouped
          />
          <Stepper
            label="Lots" value={lots}
            onChange={setLots}
            step={(cur, dir) => cur + dir}
            min={1}
            hint={lotsHint}
          />
        </div>

        {/* drag how many: bounded by cash (buy) or holdings (sell) */}
        {sliderMax != null && (
          <div className="flex items-center gap-3">
            <input
              type="range" className="lot-slider" min={1}
              max={Math.max(1, sliderMax)}
              step={1}
              disabled={sliderMax < 1}
              value={Math.min(lotsOk ? lotsNum : 1, Math.max(1, sliderMax))}
              onChange={(e) => setLots(e.target.value)}
              style={
                {
                  "--fill":
                    sliderMax > 1
                      ? `${(((lotsOk ? Math.min(lotsNum, sliderMax) : 1) - 1) / (sliderMax - 1)) * 100}%`
                      : "0%",
                } as React.CSSProperties
              }
              aria-label="Lots"
            />
            <span className="tnum shrink-0 text-xs text-ink-3">
              max {fmtNum(sliderMax)}
            </span>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <Field
            label="Fee (%)" type="number" min={0}
            max={10}
            step={0.01}
            value={feePct}
            onChange={(e) => {
              setFeePct(e.target.value);
              feePctTouched.current = true;
            }}
            hint={
              feeRp != null
                ? `= ${fmtRp(feeRp)}`
                : "brokers charge ~0.15% buy · 0.25% sell"
            }
          />
          <Field
            label="Date" type="date" value={date}
            max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>

        <Field
          label="Note (optional)" value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Why this trade?"
        />

        {insufficient &&
          (cashTracked ? (
            <ErrorNote
              message={`Insufficient cash: ${fmtRp(total! - cashBalance)} short. Deposit more from the portfolio page, or reduce the order.`}
            />
          ) : (
            <ErrorNote
              message="This portfolio has no cash yet. Use the Cash button on the portfolio page to deposit before buying."
            />
          ))}

        {error && <ErrorNote message={error} />}

        {/* the figure and the control that commits it, on one line — the
            total was previously a row above the buttons and below the fold */}
        <div className="flex flex-wrap items-end justify-between gap-4 border-t border-line pt-4">
          <div>
            <p className="w-wide text-[10px] font-bold uppercase tracking-[0.14em] text-ink-3">
              {type === "BUY" ? "Total cost, incl. fee" : "Est. proceeds, after fee"}
            </p>
            <p
              className={`tnum w-condensed mt-2 text-[30px] font-extrabold leading-none tracking-[-0.02em] ${insufficient ? "text-neg" : "text-ink"}`}
            >
              {total == null ? "—" : fmtRp(total)}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            {/* the commit button restates the side, so the mode is carried by
                the control that acts on it and not only by the toggle above */}
            <Button
              variant={type === "BUY" ? "buy" : "sell"}
              onClick={submit}
              busy={busy}
              disabled={insufficient}
            >
              {type === "BUY" ? "Record buy" : "Record sell"}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
