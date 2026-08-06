import { Clock, MagnifyingGlass } from "@phosphor-icons/react";
import { useEffect, useId, useRef, useState } from "react";
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
  const listRef = useRef<HTMLUListElement>(null);
  const listId = useId();
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

  // keep the highlighted row in view as the arrows walk a long result list
  useEffect(() => {
    if (!open || !listRef.current) return;
    listRef.current
      .querySelector<HTMLElement>(`[data-idx="${activeIdx}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [activeIdx, open]);

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
        weight="light" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3"
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
        placeholder="Search stocks" aria-label="Search stocks" role="combobox" aria-expanded={open && rows.length > 0}
        aria-controls={listId}
        aria-autocomplete="list" aria-activedescendant={
          open && rows[activeIdx] ? `${listId}-${activeIdx}` : undefined
        }
        className="w-full bg-panel-2 py-2 pl-8 pr-8 text-[13px] text-ink ring-1 ring-transparent placeholder:text-ink-3 outline-none transition-shadow focus:bg-panel focus:ring-2 focus:ring-accent"
      />
      <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 px-1.5 py-0.5 text-[10px] font-bold text-ink-3 ring-1 ring-line-2 sm:block">
        /
      </kbd>

      {open && rows.length > 0 && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden bg-panel ring-1 ring-ink">
          {!hasQuery && (
            <p className="w-wide flex items-center gap-1.5 border-b border-line px-3 pb-2 pt-2.5 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-3">
              <Clock size={11} weight="bold" /> Recent
            </p>
          )}
          <ul
            ref={listRef}
            id={listId}
            role="listbox" aria-label={hasQuery ? "Search results" : "Recent tickers"}
            className="max-h-72 overflow-y-auto py-1"
          >
            {rows.map((r, i) => (
              <li
                key={r.ticker}
                id={`${listId}-${i}`}
                data-idx={i}
                role="option" aria-selected={i === activeIdx}
              >
                <button
                  type="button" tabIndex={-1}
                  onClick={() => select(r.ticker, r.name)}
                  onMouseEnter={() => setActive(i)}
                  className={
                    "flex w-full items-baseline gap-3 px-3 py-2 text-left transition-colors " +
                    (i === activeIdx ? "bg-panel-2" : "")
                  }
                >
                  <span className="w-wide text-[13px] font-bold uppercase tracking-[0.06em] text-ink">
                    {r.ticker}
                  </span>
                  <span className="truncate text-[11px] text-ink-3">{r.name}</span>
                  {r.price != null && (
                    <span className="tnum ml-auto shrink-0 text-[11px] text-ink-2">
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
