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
  realized_pnl: number;
  as_of: string | null; // quote time; null when priced at last close
  last_close_date: string | null;
}

export interface Holdings {
  portfolio_id: string;
  holdings: Holding[];
  totals: {
    cost_basis: number;
    market_value: number | null;
    unrealized_pnl: number | null;
    realized_pnl: number;
    unpriced_holdings: number;
    cash_balance: number;
    cash_tracked: boolean;
  };
}

export interface CashFlowEntry {
  id: string;
  type: "DEPOSIT" | "WITHDRAW";
  amount: number;
  occurred_at: string;
  note: string | null;
}

export interface CashSummary {
  balance: number;
  tracked: boolean;
  flows: CashFlowEntry[];
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

export interface SecurityStats {
  computed_at: string;
  return_1d_pct: number | null;
  return_1w_pct: number | null;
  return_1mo_pct: number | null;
  return_ytd_pct: number | null;
  return_1y_pct: number | null;
  return_5y_pct: number | null;
  high_52w: number | null;
  low_52w: number | null;
  high_all: number | null;
  low_all: number | null;
  avg_volume_3mo: number | null;
  volatility_1y_pct: number | null;
  max_drawdown_1y_pct: number | null;
  beta_1y: number | null;
}

export interface ExtraStats {
  enterprise_value: number | null;
  forward_pe: number | null;
  price_to_sales: number | null;
  price_to_book: number | null;
  ev_to_revenue: number | null;
  ev_to_ebitda: number | null;
  peg_ratio: number | null;
  earnings_yield_pct: number | null;
  price_to_cashflow: number | null;
  price_to_fcf: number | null;
  profit_margin_pct: number | null;
  operating_margin_pct: number | null;
  gross_margin_pct: number | null;
  ebitda_margin_pct: number | null;
  roa_pct: number | null;
  roe_pct: number | null;
  revenue_per_share: number | null;
  cash_per_share: number | null;
  fcf_per_share: number | null;
  net_debt: number | null;
  quick_ratio: number | null;
  revenue: number | null;
  revenue_growth_pct: number | null;
  ebitda: number | null;
  net_income: number | null;
  earnings_growth_pct: number | null;
  total_cash: number | null;
  total_debt: number | null;
  debt_to_equity_pct: number | null;
  current_ratio: number | null;
  operating_cash_flow: number | null;
  free_cash_flow: number | null;
  shares_outstanding: number | null;
  float_shares: number | null;
  held_insiders_pct: number | null;
  held_institutions_pct: number | null;
  avg_volume_10d: number | null;
  forward_dividend_rate: number | null;
  trailing_dividend_yield_pct: number | null;
  five_year_avg_dividend_yield_pct: number | null;
  payout_ratio_pct: number | null;
  ex_dividend_date: string | null;
  financial_currency: string | null;
}

export interface Fundamentals {
  market_cap: number | null;
  pe_ratio: number | null;
  eps: number | null;
  dividend_yield_pct: number | null;
  book_value: number | null;
  extra: ExtraStats | null;
  last_updated: string;
}

export interface SecurityDetail {
  ticker: string;
  name: string;
  sector: string | null;
  board: string | null;
  is_active: boolean;
  has_history: boolean;
  quote_price: number | null;
  quote_change_pct: number | null;
  quote_as_of: string | null;
  last_close: number | null;
  last_close_date: string | null;
  stats: SecurityStats | null;
  fundamentals: Fundamentals | null;
}

export interface StatementPeriod {
  period_end: string;
  items: Record<string, number>;
}

export interface DerivedMetrics {
  interest_coverage: number | null;
  financial_leverage: number | null;
  lt_debt_to_equity: number | null;
  liabilities_to_equity: number | null;
  debt_to_assets: number | null;
  asset_turnover: number | null;
  roce_pct: number | null;
  days_sales_outstanding: number | null;
  days_inventory: number | null;
  days_payables: number | null;
  cash_conversion_cycle: number | null;
  fcf_ttm: number | null;
  price_to_fcf_ttm: number | null;
  altman_z: number | null;
  piotroski_f: number | null;
  piotroski_max: number | null;
}

export interface Financials {
  ticker: string;
  currency: string | null;
  annual: StatementPeriod[];
  quarterly: StatementPeriod[];
  derived: DerivedMetrics;
}

export interface StockPricePoint {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number | null;
  ihsg: number | null;
}

export interface StockPrices {
  ticker: string;
  range: string;
  points: StockPricePoint[];
}

export interface PositionRow {
  portfolio_id: string;
  portfolio_name: string;
  lots: number;
  shares: number;
  avg_cost_per_share: number;
  cost_basis: number;
  market_value: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  pct_of_portfolio: number | null;
}

export interface PositionTxn {
  executed_at: string;
  type: TxnType;
  lots: number;
  price_per_share: number;
  portfolio_name: string;
}

export interface StockPosition {
  held: boolean;
  positions: PositionRow[];
  transactions: PositionTxn[];
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

  updateTransaction: (
    portfolioId: string,
    txnId: string,
    txn: Omit<NewTransaction, "ticker">,
  ) =>
    request<Transaction>(`/portfolios/${portfolioId}/transactions/${txnId}`, {
      method: "PATCH",
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

  cash: (id: string) => request<CashSummary>(`/portfolios/${id}/cash`),

  addCashFlow: (
    id: string,
    flow: {
      type: "DEPOSIT" | "WITHDRAW";
      amount: number;
      occurred_at?: string;
      note?: string | null;
    },
  ) =>
    request<CashSummary>(`/portfolios/${id}/cash`, {
      method: "POST",
      body: flow,
    }),

  deleteCashFlow: (portfolioId: string, flowId: string) =>
    request<void>(`/portfolios/${portfolioId}/cash/${flowId}`, {
      method: "DELETE",
    }),

  searchSecurities: (q: string) =>
    request<SearchResult[]>(`/securities/search?q=${encodeURIComponent(q)}`),

  ensurePrices: (ticker: string) =>
    request<{ status: "ready" | "queued" | "unavailable" }>(
      `/securities/${encodeURIComponent(ticker)}/ensure-prices`,
      { method: "POST" },
    ),

  securityDetail: (ticker: string) =>
    request<SecurityDetail>(`/securities/${encodeURIComponent(ticker)}`),

  securityPrices: (ticker: string, range: RangeKey) =>
    request<StockPrices>(
      `/securities/${encodeURIComponent(ticker)}/prices?range=${range}`,
    ),

  securityPosition: (ticker: string) =>
    request<StockPosition>(`/securities/${encodeURIComponent(ticker)}/position`),

  securityFinancials: (ticker: string) =>
    request<Financials>(`/securities/${encodeURIComponent(ticker)}/financials`),

  /** Close on a date (or the last trading day before it) — prices
   *  back-dated transactions. */
  securityCloseOn: (ticker: string, on: string) =>
    request<{
      ticker: string;
      requested: string;
      trade_date: string | null;
      close: number | null;
    }>(`/securities/${encodeURIComponent(ticker)}/close?on=${on}`),
};
