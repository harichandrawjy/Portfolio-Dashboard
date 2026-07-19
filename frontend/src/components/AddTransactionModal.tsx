import { MagnifyingGlass } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

import { api, type NewTransaction, type SearchResult, type TxnType } from "../api/client";
import { useDebounced } from "../lib/hooks";
import { fmtNum, fmtRp } from "../lib/format";
import { Button, ErrorNote, Field, Modal } from "./ui";

const SHARES_PER_LOT = 100;

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

  // ---- autocomplete ------------------------------------------------
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const debouncedQuery = useDebounced(ticker, 250);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (tickerPicked || debouncedQuery.trim().length < 1) {
      setResults([]);
      return;
    }
    let cancelled = false;
    api.searchSecurities(debouncedQuery.trim()).then(
      (r) => {
        if (!cancelled) {
          setResults(r);
          setOpen(true);
        }
      },
      () => {
        if (!cancelled) setResults([]);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery, tickerPicked]);

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

  /** A picked ticker with no local price: enqueue the lazy backfill, then
   *  poll the local search until its price lands (a few seconds). */
  const fetchPriceInBackground = async (ticker: string) => {
    const token = ++pollToken.current;
    setPriceHint("No local price yet · fetching…");
    try {
      const res = await api.ensurePrices(ticker);
      if (res.status === "unavailable") {
        if (pollToken.current === token)
          setPriceHint("Price service unavailable · enter the price manually");
        return;
      }
      for (let attempt = 0; attempt < 8; attempt++) {
        await new Promise((r) => setTimeout(r, 1500));
        if (pollToken.current !== token) return;
        const hits = await api.searchSecurities(ticker);
        const hit = hits.find((h) => h.ticker === ticker);
        if (hit?.last_price != null) {
          if (pollToken.current !== token) return;
          // fill only if the user still hasn't typed a price themselves
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

  const lotsNum = parseInt(lots, 10);
  const shares = Number.isFinite(lotsNum) && lotsNum > 0 ? lotsNum * SHARES_PER_LOT : null;

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
                "rounded-[10px] py-2 text-sm font-semibold ring-1 transition-all duration-200 active:scale-[0.98] " +
                (type === t
                  ? t === "BUY"
                    ? "bg-pos/15 text-pos ring-pos/40"
                    : "bg-neg/15 text-neg ring-neg/40"
                  : "bg-panel-2 text-ink-3 ring-line hover:text-ink-2")
              }
            >
              {t === "BUY" ? "Buy" : "Sell"}
            </button>
          ))}
        </div>

        {/* Ticker autocomplete */}
        <div ref={boxRef} className="relative">
          <label className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-ink-2">Ticker</span>
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
                }}
                onFocus={() => results.length > 0 && setOpen(true)}
                placeholder="BBCA, TLKM, or a company name"
                autoFocus
                className="w-full rounded-[8px] bg-panel-2 py-2 pl-9 pr-3 font-mono text-sm text-ink ring-1 ring-line placeholder:font-sans placeholder:text-ink-3 outline-none focus:ring-2 focus:ring-accent/60"
              />
            </div>
          </label>
          {open && results.length > 0 && (
            <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-[8px] bg-panel py-1 ring-1 ring-line-2 shadow-[0_24px_48px_-16px_rgb(22_24_29/0.35)]">
              {results.map((r) => (
                <li key={r.ticker}>
                  <button
                    onClick={() => {
                      setTicker(r.ticker);
                      setTickerPicked(true);
                      setOpen(false);
                      pollToken.current += 1; // stop any previous poll
                      if (price === "" || priceAutofilled)
                        userTypedPrice.current = false;
                      if (r.last_price != null) {
                        if (price === "" || priceAutofilled) {
                          setPrice(String(r.last_price));
                          setPriceAutofilled(true);
                          setPriceHint("Last known price · edit freely");
                        }
                      } else {
                        void fetchPriceInBackground(r.ticker);
                      }
                    }}
                    className="flex w-full items-baseline gap-3 px-3 py-2 text-left transition-colors hover:bg-ink/5"
                  >
                    <span className="font-mono text-sm font-semibold text-ink">
                      {r.ticker}
                    </span>
                    <span className="truncate text-xs text-ink-3">{r.name}</span>
                    <span className="ml-auto shrink-0">
                      {r.last_price != null ? (
                        <span className="tnum font-mono text-xs text-ink-2">
                          {fmtRp(r.last_price)}
                        </span>
                      ) : (
                        <span className="text-[11px] text-ink-3">
                          {r.sector ?? ""}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              ))}
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
            hint={shares != null ? `= ${fmtNum(shares)} shares` : "1 lot = 100 shares"}
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
