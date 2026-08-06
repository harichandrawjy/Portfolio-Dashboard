import { useCallback, useEffect, useRef, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** HTTP status when the rejection carried one, so callers can tell a 404
   *  ("no such thing") from a 500 or a dropped connection. */
  status: number | null;
}

/**
 * Tiny data-fetching hook: runs `fn` when `deps` change, exposes
 * { data, loading, error, reload }. Stale responses are discarded.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    loading: true,
    error: null,
    status: null,
  });
  const runId = useRef(0);

  const run = useCallback(() => {
    const id = ++runId.current;
    setState((s) => ({ ...s, loading: true, error: null, status: null }));
    fn().then(
      (data) => {
        if (runId.current === id)
          setState({ data, loading: false, error: null, status: null });
      },
      (err: Error) => {
        if (runId.current !== id) return;
        const s = (err as { status?: unknown }).status;
        setState({
          data: null,
          loading: false,
          error: err.message,
          status: typeof s === "number" ? s : null,
        });
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
  }, [run]);

  return { ...state, reload: run };
}

/** Debounce a changing value (used by the ticker autocomplete). */
export function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}
