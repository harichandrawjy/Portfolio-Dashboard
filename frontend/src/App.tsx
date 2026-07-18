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
      <header className="border-b border-line bg-panel/60 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center justify-between px-4">
          <Link to="/" className="text-[15px] font-semibold tracking-tight text-ink">
            Arus<span className="text-accent">.</span>
          </Link>
          <div className="flex items-center gap-3 text-[13px] text-ink-3">
            <span className="hidden sm:inline">
              {user?.display_name || user?.email}
            </span>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 rounded-[8px] px-2 py-1 transition-colors hover:bg-white/5 hover:text-ink-2"
            >
              <SignOut size={14} weight="light" /> Sign out
            </button>
          </div>
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
