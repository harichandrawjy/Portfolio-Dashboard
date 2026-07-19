import { SignOut } from "@phosphor-icons/react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { RequireAuth, useAuth } from "./auth";
import { LoginPage } from "./pages/Login";
import { PortfolioDetailPage } from "./pages/PortfolioDetail";
import { PortfoliosPage } from "./pages/Portfolios";
import { StockPage } from "./pages/Stock";

function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-[100dvh]">
      <header className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-4">
        <Link
          to="/"
          className="text-[16px] font-semibold tracking-tight text-ink outline-none focus-visible:text-accent"
        >
          Arus<span className="text-accent">.</span>
        </Link>
        <div className="flex items-center gap-3">
          <span className="tnum hidden font-mono text-xs text-ink-3 sm:inline">
            {user?.display_name || user?.email}
          </span>
          <button
            onClick={logout}
            className="flex items-center gap-1.5 rounded-[8px] px-2 py-1 text-[13px] text-ink-3 outline-none transition-colors hover:bg-white/5 hover:text-ink-2 focus-visible:ring-2 focus-visible:ring-accent/70"
          >
            <SignOut size={14} weight="light" /> Sign out
          </button>
        </div>
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
