import { SignOut } from "@phosphor-icons/react";
import { Suspense, lazy } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { RequireAuth, useAuth } from "./auth";
import { TickerSearch } from "./components/TickerSearch";
import { Colophon, Skeleton } from "./components/ui";

// Routes load on demand: Recharts rides with the portfolio page and
// Lightweight Charts with the stock page, so neither ships to someone who
// only opens the login screen.
const LoginPage = lazy(() =>
  import("./pages/Login").then((m) => ({ default: m.LoginPage })),
);
const PortfoliosPage = lazy(() =>
  import("./pages/Portfolios").then((m) => ({ default: m.PortfoliosPage })),
);
const PortfolioDetailPage = lazy(() =>
  import("./pages/PortfolioDetail").then((m) => ({
    default: m.PortfolioDetailPage,
  })),
);
const StockPage = lazy(() =>
  import("./pages/Stock").then((m) => ({ default: m.StockPage })),
);
// Where the emailed links land. Public by necessity — the visitor has no
// session yet, and the token in the URL is what stands in for one.
const VerifyPage = lazy(() =>
  import("./pages/AuthLink").then((m) => ({ default: m.VerifyPage })),
);
const ResetPage = lazy(() =>
  import("./pages/AuthLink").then((m) => ({ default: m.ResetPage })),
);

/** Holds the page's shape while its chunk arrives, inside the 1200 measure. */
function PageFallback() {
  return (
    <div className="mx-auto w-full max-w-[1200px] px-4 pt-8">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-4 h-24 w-80" />
      <Skeleton className="mt-8 h-72 w-full" />
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  return (
    // a column with the main region growing: on a short page that pushes the
    // colophon to the bottom of the viewport, so no blank strip is ever left
    // under it, and on a long page it simply follows the content
    <div className="flex min-h-[100dvh] flex-col">
      {/* masthead: a nameplate ruled off from the page by a single heavy
          black line. The wordmark is set in the heaviest cut, wide and
          uppercase, closed by a solid accent square. */}
      <header className="sticky top-0 z-30 border-b-2 border-ink bg-bg">
        <div className="mx-auto max-w-[1200px] px-4">
          <div className="flex h-16 items-center gap-4">
            {/* a colour shift alone was the only focus cue here; every other
                control in the app gets the accent ring */}
            <Link
              to="/" className="group shrink-0 py-1 outline-none focus-visible:ring-2 focus-visible:ring-accent" aria-label="Arus — home"
            >
              <span className="flow-underline w-wide flex items-baseline gap-1.5 text-[19px] font-extrabold uppercase leading-none tracking-[0.16em] text-ink transition-colors group-focus-visible:text-accent">
                Arus
                <span aria-hidden className="block h-2 w-2 bg-accent" />
              </span>
            </Link>
            <div className="flex flex-1 justify-center px-2">
              <TickerSearch />
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <span className="tnum hidden text-[11px] uppercase tracking-[0.1em] text-ink-3 sm:inline">
                {user?.display_name || user?.email}
              </span>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 px-2.5 py-2 text-[11px] font-bold uppercase tracking-[0.12em] text-ink-3 outline-none transition-colors hover:bg-ink hover:text-bg focus-visible:ring-2 focus-visible:ring-accent"
              >
                <SignOut size={14} weight="bold" /> Sign out
              </button>
            </div>
          </div>
        </div>
      </header>
      {/* the boundary sits inside the shell, so the masthead stays put while
          a page chunk loads instead of the screen going blank */}
      <main className="flex-1">
        <Suspense fallback={<PageFallback />}>{children}</Suspense>
      </main>
      <Colophon />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/verify" element={<VerifyPage />} />
        <Route path="/reset" element={<ResetPage />} />
        <Route
          path="/" element={
            <RequireAuth>
              <Shell>
                <PortfoliosPage />
              </Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/portfolios/:id" element={
            <RequireAuth>
              <Shell>
                <PortfolioDetailPage />
              </Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/stocks/:ticker" element={
            <RequireAuth>
              <Shell>
                <StockPage />
              </Shell>
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
