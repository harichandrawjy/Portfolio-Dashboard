import { Clock, MagnifyingGlass } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, type SearchResult } from "../api/client";
import { fmtRp } from "../lib/format";
import { useDebounced } from "../lib/hooks";

/** Recently picked tickers, persisted per browser. */
const RECENTS_KEY = "arus.recentTickers";
const RECENTS_MAX = 6;

interface Recent {
  ticker: string;
  name: string;
}

function loadRecents(): Recent[] {
  try {
    const raw = localStorage.getItem(RECENTS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function pushRecent(r: Recent): Recent[] {
  const next = [r, ...loadRecents().filter((x) => x.ticker !== r.ticker)].slice(
    0,
    RECENTS_MAX,
  );
  localStorage.setItem(RECENTS_KEY, JSON.stringify(next));
  return next;
}

interface Row {
  ticker: string;
  name: string;
  price: number | null;
}

/** Masthead search over the whole IDX universe; picking a result opens the
 *  stock detail page. Empty + focused shows recently picked tickers.
 *  Press "/" anywhere to focus. */
export function TickerSearch() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [recents, setRecents] = useState<Recent[]>(() => loadRecents());
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const debounced = useDebounced(q, 200);
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const hasQuery = q.trim().length > 0;
  const rows: Row[] = hasQuery
    ? results.map((r) => ({ ticker: r.ticker, name: r.name, price: r.last_price }))
    : recents.map((r) => ({ ticker: r.ticker, name: r.name, price: null }));
  const activeIdx = Math.min(active, Math.max(0, rows.length - 1));

  useEffect(() => {
    if (debounced.trim().length < 1) {
      setResults([]);
      return;
    }
    let cancelled = false;
    api.searchSecurities(debounced.trim()).then(
      (r) => {
        if (!cancelled) {
          setResults(r);
          setActive(0);
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
  }, [debounced]);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node))
        setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, []);

  // "/" focuses search unless the user is already typing somewhere
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/") return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      e.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const select = (ticker: string, name: string) => {
    setRecents(pushRecent({ ticker, name }));
    setQ("");
    setResults([]);
    setOpen(false);
    inputRef.current?.blur();
    navigate(`/stocks/${ticker}`);
  };

  return (
    <div ref={boxRef} className="relative w-full max-w-[320px]">
      <MagnifyingGlass
        size={14}
        weight="light"
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3"
      />
      <input
        ref={inputRef}
        value={q}
        onChange={(e) => {
          setQ(e.target.value.toUpperCase());
          setActive(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(a + 1, rows.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter" && open && rows[activeIdx]) {
            select(rows[activeIdx].ticker, rows[activeIdx].name);
          } else if (e.key === "Escape") {
            setOpen(false);
            inputRef.current?.blur();
          }
        }}
        placeholder="Search stocks"
        aria-label="Search stocks"
        className="w-full rounded-[6px] bg-panel py-1.5 pl-8 pr-8 font-mono text-[13px] text-ink ring-1 ring-line placeholder:font-sans placeholder:text-ink-3 outline-none transition-shadow focus:ring-2 focus:ring-accent/60"
      />
      <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded-[4px] px-1 font-mono text-[11px] text-ink-3 ring-1 ring-line sm:block">
        /
      </kbd>

      {open && rows.length > 0 && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-[8px] bg-panel ring-1 ring-line-2 shadow-[0_24px_48px_-16px_rgb(23_30_54/0.32)]">
          {!hasQuery && (
            <p className="flex items-center gap-1.5 px-3 pb-1 pt-2 text-[11px] font-medium text-ink-3">
              <Clock size={11} weight="light" /> Recent
            </p>
          )}
          <ul className="max-h-72 overflow-y-auto py-1">
            {rows.map((r, i) => (
              <li key={r.ticker}>
                <button
                  onClick={() => select(r.ticker, r.name)}
                  onMouseEnter={() => setActive(i)}
                  className={
                    "flex w-full items-baseline gap-3 px-3 py-2 text-left transition-colors " +
                    (i === activeIdx ? "bg-ink/5" : "")
                  }
                >
                  <span className="font-mono text-sm font-semibold text-ink">
                    {r.ticker}
                  </span>
                  <span className="truncate text-xs text-ink-3">{r.name}</span>
                  {r.price != null && (
                    <span className="tnum ml-auto shrink-0 font-mono text-xs text-ink-2">
                      {fmtRp(r.price)}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
