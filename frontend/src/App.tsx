import { SignOut } from "@phosphor-icons/react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { RequireAuth, useAuth } from "./auth";
import { TickerSearch } from "./components/TickerSearch";
import { LoginPage } from "./pages/Login";
import { PortfolioDetailPage } from "./pages/PortfolioDetail";
import { PortfoliosPage } from "./pages/Portfolios";
import { StockPage } from "./pages/Stock";

function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-[100dvh]">
      {/* masthead: a broadsheet nameplate — a thick rule that starts bold
          cobalt and fades to ink runs beneath, the wordmark's dot pulses */}
      <header className="sticky top-0 z-30 bg-bg/95">
        <div className="mx-auto max-w-[1200px] px-4">
          <div className="flex h-16 items-center gap-4">
            <Link
              to="/"
              className="group shrink-0 outline-none"
              aria-label="Arus — home"
            >
              <span className="flow-underline font-serif text-[22px] font-semibold text-ink transition-colors group-focus-visible:text-accent">
                Arus<span className="current-dot text-accent">.</span>
              </span>
            </Link>
            <div className="flex flex-1 justify-center px-2">
              <TickerSearch />
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <span className="tnum hidden font-mono text-xs text-ink-3 sm:inline">
                {user?.display_name || user?.email}
              </span>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 rounded-[6px] px-2 py-1 text-[13px] text-ink-3 outline-none transition-colors hover:bg-ink/[0.05] hover:text-ink focus-visible:ring-2 focus-visible:ring-accent/70"
              >
                <SignOut size={14} weight="light" /> Sign out
              </button>
            </div>
          </div>
        </div>
        <div className="h-0.5 w-full [background:linear-gradient(90deg,#2b3570,rgb(23_30_54/0.32)_36%,rgb(23_30_54/0.16))]" />
      </header>
      {children}
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Shell>
              <PortfoliosPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/portfolios/:id"
        element={
          <RequireAuth>
            <Shell>
              <PortfolioDetailPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/stocks/:ticker"
        element={
          <RequireAuth>
            <Shell>
              <StockPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
