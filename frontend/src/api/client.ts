/**
 * Typed API client. Every backend call in the app lives here — components
 * never fetch() directly. Paths are prefixed /api and proxied by Vite to
 * FastAPI (see vite.config.ts).
 */

const BASE = "/api";
const TOKEN_KEY = "arus.token";

let token: string | null = localStorage.getItem(TOKEN_KEY);

export function getToken(): string | null {
  return token;
}

export function setToken(t: string | null) {
  token = t;
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** FastAPI error detail is a string for app errors, an array for validation. */
function detailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const d = detail[0] as { loc?: unknown[]; msg?: string };
    const field = Array.isArray(d.loc) ? String(d.loc[d.loc.length - 1]) : "";
    return field ? `${field}: ${d.msg ?? "invalid"}` : (d.msg ?? fallback);
  }
  return fallback;
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(BASE + path, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(
      res.status,
      detailToMessage(body?.detail, `Request failed (${res.status})`),
    );
  }
  return body as T;
}

// ---------------------------------------------------------------------------
// Types (mirror backend/app/schemas.py)
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
}

export interface Portfolio {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export type TxnType = "BUY" | "SELL";

export interface Transaction {
  id: string;
  ticker: string;
  type: TxnType;
  lots: number;
  shares: number;
  price_per_share: number;
  fee: number;
  executed_at: string;
  note: string | null;
  created_at: string;
}

export interface TransactionList {
  items: Transaction[];
  total: number;
  limit: number;
  offset: number;
}

export interface Holding {
  ticker: string;
  name: string;
  shares: number;
  lots: number;
  avg_cost_per_share: number;
  cost_basis: number;
  last_price: number | null;
  market_value: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  as_of: string | null;
}

export interface Holdings {
  portfolio_id: string;
  holdings: Holding[];
  totals: {
    cost_basis: number;
    market_value: number | null;
    unrealized_pnl: number | null;
    unpriced_holdings: number;
  };
}

export type RangeKey = "1mo" | "6mo" | "1y" | "all";

export interface PerformancePoint {
  date: string;
  portfolio_value: number;
  ihsg_normalized: number | null;
}

export interface Performance {
  portfolio_id: string;
  range: string;
  points: PerformancePoint[];
}

export interface Metrics {
  portfolio_id: string;
  range: string;
  start_date: string | null;
  end_date: string | null;
  trading_days: number;
  total_return_pct: number | null;
  benchmark_return_pct: number | null;
  annualized_volatility_pct: number | null;
  sharpe_ratio: number | null;
  max_drawdown_pct: number | null;
  beta: number | null;
  risk_free_rate_pct: number;
}

export interface StockSlice {
  ticker: string;
  name: string;
  sector: string | null;
  market_value: number;
  weight_pct: number;
}

export interface SectorSlice {
  sector: string | null;
  market_value: number;
  weight_pct: number;
}

export interface ConcentrationFlag {
  type: "stock_concentration" | "sector_concentration";
  ticker: string | null;
  sector: string | null;
  weight_pct: number;
  threshold_pct: number;
}

export interface Allocation {
  portfolio_id: string;
  total_market_value: number;
  by_stock: StockSlice[];
  by_sector: SectorSlice[];
  flags: ConcentrationFlag[];
  unpriced: string[];
}

export interface SearchResult {
  ticker: string;
  name: string;
  sector: string | null;
  board: string | null;
  last_price: number | null;
}

export interface NewTransaction {
  ticker: string;
  type: TxnType;
  lots: number;
  price_per_share: number;
  fee: number;
  executed_at: string;
  note?: string | null;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const api = {
  register: (email: string, password: string, displayName?: string) =>
    request<User>("/auth/register", {
      method: "POST",
      body: { email, password, display_name: displayName || null },
    }),

  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: { email, password },
    }),

  me: () => request<User>("/me"),

  listPortfolios: () => request<Portfolio[]>("/portfolios"),

  createPortfolio: (name: string, description?: string) =>
    request<Portfolio>("/portfolios", {
      method: "POST",
      body: { name, description: description || null },
    }),

  deletePortfolio: (id: string) =>
    request<void>(`/portfolios/${id}`, { method: "DELETE" }),

  getPortfolio: (id: string) => request<Portfolio>(`/portfolios/${id}`),

  holdings: (id: string) => request<Holdings>(`/portfolios/${id}/holdings`),

  transactions: (id: string, limit = 50, offset = 0) =>
    request<TransactionList>(
      `/portfolios/${id}/transactions?limit=${limit}&offset=${offset}`,
    ),

  addTransaction: (id: string, txn: NewTransaction) =>
    request<Transaction>(`/portfolios/${id}/transactions`, {
      method: "POST",
      body: txn,
    }),

  deleteTransaction: (portfolioId: string, txnId: string) =>
    request<void>(`/portfolios/${portfolioId}/transactions/${txnId}`, {
      method: "DELETE",
    }),

  performance: (id: string, range: RangeKey) =>
    request<Performance>(`/portfolios/${id}/performance?range=${range}`),

  metrics: (id: string, range: RangeKey) =>
    request<Metrics>(`/portfolios/${id}/metrics?range=${range}`),

  allocation: (id: string) => request<Allocation>(`/portfolios/${id}/allocation`),

  searchSecurities: (q: string) =>
    request<SearchResult[]>(`/securities/search?q=${encodeURIComponent(q)}`),
};
