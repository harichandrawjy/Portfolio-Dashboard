import { MagnifyingGlass } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, type SearchResult } from "../api/client";
import { fmtRp } from "../lib/format";
import { useDebounced } from "../lib/hooks";

/** Masthead search over the whole IDX universe; picking a result opens the
 *  stock detail page. Press "/" anywhere to focus. */
export function TickerSearch() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const debounced = useDebounced(q, 200);
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (debounced.trim().length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    let cancelled = false;
    api.searchSecurities(debounced.trim()).then(
      (r) => {
        if (!cancelled) {
          setResults(r);
          setActive(0);
          setOpen(r.length > 0);
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

  const go = (ticker: string) => {
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
        onChange={(e) => setQ(e.target.value.toUpperCase())}
        onFocus={() => results.length > 0 && setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(a + 1, results.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter" && open && results[active]) {
            go(results[active].ticker);
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

      {open && results.length > 0 && (
        <ul className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-[8px] bg-panel py-1 ring-1 ring-line-2 shadow-[0_24px_48px_-16px_rgb(22_24_29/0.35)]">
          {results.map((r, i) => (
            <li key={r.ticker}>
              <button
                onClick={() => go(r.ticker)}
                onMouseEnter={() => setActive(i)}
                className={
                  "flex w-full items-baseline gap-3 px-3 py-2 text-left transition-colors " +
                  (i === active ? "bg-ink/5" : "")
                }
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
  );
}
