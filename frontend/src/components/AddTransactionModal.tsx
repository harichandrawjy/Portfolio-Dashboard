import { MagnifyingGlass } from "@phosphor-icons/react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  api,
  type Holding,
  type NewTransaction,
  type SearchResult,
  type TxnType,
} from "../api/client";
import { useDebounced } from "../lib/hooks";
import { fmtNum, fmtRp } from "../lib/format";
import { Button, ErrorNote, Field, Modal } from "./ui";

const SHARES_PER_LOT = 100;

/** One dropdown row, whether it came from universe search (BUY) or the
 *  portfolio's own holdings (SELL). */
interface Suggestion {
  ticker: string;
  name: string;
  last_price: number | null;
  heldLots: number | null;
  sector: string | null;
}

export function AddTransactionModal({
  portfolioId,
  onClose,
  onSaved,
}: {
  portfolioId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [type, setType] = useState<TxnType>("BUY");
  const [ticker, setTicker] = useState("");
  const [tickerPicked, setTickerPicked] = useState(false);
  const [lots, setLots] = useState("1");
  const [price, setPrice] = useState("");
  // true while the price came from autocomplete; a manual edit clears it so
  // we never overwrite something the user typed
  const [priceAutofilled, setPriceAutofilled] = useState(false);
  const [priceHint, setPriceHint] = useState<string | null>(null);
  // set the moment the user types a price by hand; async fills check it
  const userTypedPrice = useRef(false);
  // bumping this cancels any in-flight price poll (new pick, or unmount)
  const pollToken = useRef(0);
  const [fee, setFee] = useState("0");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // ---- current holdings (the only sellable things) -----------------
  const [held, setHeld] = useState<Holding[] | null>(null);
  useEffect(() => {
    api.holdings(portfolioId).then(
      (h) => setHeld(h.holdings),
      () => setHeld([]),
    );
  }, [portfolioId]);

  // ---- autocomplete ------------------------------------------------
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const debouncedQuery = useDebounced(ticker, 250);
  const boxRef = useRef<HTMLDivElement>(null);

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

  // switching Buy/Sell resets the dropdown, not the user's input
  useEffect(() => {
    setOpen(false);
    setSearchResults([]);
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
      pollToken.current += 1; // cancel polls when the modal unmounts
    };
  }, []);

  /** A picked ticker with no local price (BUY only): enqueue the lazy
   *  backfill, then poll the local search until its price lands. */
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

  const pickSuggestion = (s: Suggestion) => {
    setTicker(s.ticker);
    setTickerPicked(true);
    setOpen(false);
    pollToken.current += 1; // stop any previous poll
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
  };

  const lotsNum = parseInt(lots, 10);
  const shares =
    Number.isFinite(lotsNum) && lotsNum > 0 ? lotsNum * SHARES_PER_LOT : null;

  const heldPosition = held?.find((h) => h.ticker === ticker.trim().toUpperCase());
  const sellingUnheld =
    type === "SELL" && held !== null && ticker.trim() !== "" && tickerPicked && !heldPosition;

  const lotsHint =
    type === "SELL" && heldPosition
      ? `= ${fmtNum(shares)} shares · you hold ${fmtNum(heldPosition.lots)} lots`
      : shares != null
        ? `= ${fmtNum(shares)} shares`
        : "1 lot = 100 shares";

  const submit = async () => {
    setError(null);
    const priceNum = parseInt(price, 10);
    const feeNum = parseInt(fee || "0", 10);
    if (!ticker.trim()) return setError("Pick a ticker first.");
    if (!Number.isFinite(lotsNum) || lotsNum < 1)
      return setError("Lots must be a whole number of at least 1.");
    if (!Number.isFinite(priceNum) || priceNum < 1)
      return setError("Price per share must be a positive whole-rupiah amount.");
    if (!Number.isFinite(feeNum) || feeNum < 0)
      return setError("Fee cannot be negative.");

    const txn: NewTransaction = {
      ticker: ticker.trim().toUpperCase(),
      type,
      lots: lotsNum,
      price_per_share: priceNum,
      fee: feeNum,
      executed_at: date,
      note: note.trim() || null,
    };
    setBusy(true);
    try {
      await api.addTransaction(portfolioId, txn);
      onSaved();
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
        {/* BUY / SELL toggle */}
        <div className="grid grid-cols-2 gap-2">
          {(["BUY", "SELL"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={
                "rounded-[6px] py-2 text-sm font-semibold ring-1 transition-all duration-200 active:scale-[0.98] " +
                (type === t
                  ? t === "BUY"
                    ? "bg-pos/10 text-pos ring-pos/50"
                    : "bg-neg/10 text-neg ring-neg/50"
                  : "bg-panel text-ink-3 ring-line hover:text-ink-2")
              }
            >
              {t === "BUY" ? "Buy" : "Sell"}
            </button>
          ))}
        </div>

        {/* Ticker: universe search when buying, own holdings when selling */}
        <div ref={boxRef} className="relative">
          <label className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-ink-2">
              {type === "SELL" ? "Ticker (from this portfolio)" : "Ticker"}
            </span>
            <div className="relative">
              <MagnifyingGlass
                size={15}
                weight="light"
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3"
              />
              <input
                value={ticker}
                onChange={(e) => {
                  setTicker(e.target.value.toUpperCase());
                  setTickerPicked(false);
                  if (type === "SELL") setOpen(true);
                }}
                onFocus={() => {
                  if (type === "SELL" || suggestions.length > 0) setOpen(true);
                }}
                placeholder={
                  type === "SELL"
                    ? "Pick a holding to sell"
                    : "BBCA, TLKM, or a company name"
                }
                autoFocus
                className="w-full rounded-[6px] bg-panel py-2 pl-9 pr-3 font-mono text-sm text-ink ring-1 ring-line placeholder:font-sans placeholder:text-ink-3 outline-none focus:ring-2 focus:ring-accent/60"
              />
            </div>
            {sellingUnheld && (
              <span className="text-xs text-warn">
                {ticker.trim().toUpperCase()} is not held in this portfolio.
              </span>
            )}
          </label>

          {open && (
            <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-[8px] bg-panel py-1 ring-1 ring-line-2 shadow-[0_24px_48px_-16px_rgb(22_24_29/0.35)]">
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
                suggestions.map((s) => (
                  <li key={s.ticker}>
                    <button
                      onClick={() => pickSuggestion(s)}
                      className="flex w-full items-baseline gap-3 px-3 py-2 text-left transition-colors hover:bg-ink/5"
                    >
                      <span className="font-mono text-sm font-semibold text-ink">
                        {s.ticker}
                      </span>
                      <span className="truncate text-xs text-ink-3">
                        {s.name}
                      </span>
                      <span className="ml-auto shrink-0">
                        {s.heldLots != null ? (
                          <span className="tnum font-mono text-xs text-ink-2">
                            {fmtNum(s.heldLots)} lots
                          </span>
                        ) : s.last_price != null ? (
                          <span className="tnum font-mono text-xs text-ink-2">
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

        <div className="grid grid-cols-2 gap-4">
          <Field
            label="Lots"
            type="number"
            min={1}
            step={1}
            value={lots}
            onChange={(e) => setLots(e.target.value)}
            hint={lotsHint}
          />
          <Field
            label="Price per share (Rp)"
            type="number"
            min={1}
            step={1}
            value={price}
            onChange={(e) => {
              setPrice(e.target.value);
              setPriceAutofilled(false);
              setPriceHint(null);
              userTypedPrice.current = true;
            }}
            placeholder="6500"
            hint={priceHint ?? undefined}
          />
          <Field
            label="Fee (Rp)"
            type="number"
            min={0}
            step={1}
            value={fee}
            onChange={(e) => setFee(e.target.value)}
          />
          <Field
            label="Date"
            type="date"
            value={date}
            max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>

        <Field
          label="Note (optional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Why this trade?"
        />

        {error && <ErrorNote message={error} />}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} busy={busy}>
            {type === "BUY" ? "Record buy" : "Record sell"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
