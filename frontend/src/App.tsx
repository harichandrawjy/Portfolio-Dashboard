import { SignOut } from "@phosphor-icons/react";
import { Suspense, lazy } from "react";
import { Link, NavLink, Navigate, Route, Routes } from "react-router-dom";

import { RequireAuth, useAuth } from "./auth";
import { TickerSearch } from "./components/TickerSearch";
import { Colophon, Skeleton } from "./components/ui";

// Routes load on demand: Recharts rides with the portfolio page and
// Lightweight Charts with the stock page, so neither ships to someone who
// only opens the login screen.
const LoginPage = lazy(() =>
  import("./pages/Login").then((m) => ({ default: m.LoginPage })),
);
const ContactPage = lazy(() =>
  import("./pages/Contact").then((m) => ({ default: m.ContactPage })),
);
const HomePage = lazy(() =>
  import("./pages/Home").then((m) => ({ default: m.HomePage })),
);
const ConsultingPage = lazy(() =>
  import("./pages/Consulting").then((m) => ({ default: m.ConsultingPage })),
);
const ResearchPage = lazy(() =>
  import("./pages/Research").then((m) => ({ default: m.ResearchPage })),
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

/** The three things Arus does. Labels are short because a masthead is
 *  scanned, not read — the full name of each ("Portfolio demo and
 *  optimisation", "Market research") is the page's own headline, where
 *  there is room for it. `end` on the portfolio entry stops it matching
 *  every route, since its path is "/". */
const SECTIONS = [
  // `end: false` on the portfolio entry so the section still reads as current
  // while you are inside a single portfolio at /portfolios/:id.
  { to: "/portfolios", label: "Portfolio", end: false },
  { to: "/consulting", label: "Consulting", end: false },
  { to: "/research", label: "Research", end: false },
];

function SectionNav({ className = "" }: { className?: string }) {
  return (
    <nav aria-label="Sections" className={className}>
      {SECTIONS.map(({ to, label, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            "flow-underline relative py-1 text-[11px] font-bold uppercase tracking-[0.12em] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent " +
            (isActive ? "text-ink" : "text-ink-3 hover:text-ink")
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
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
            {/* Inline once there is room. Below md it moves to its own row
                rather than collapsing into a hamburger: three items is not
                enough to hide behind a menu, and this system has no drawer
                vocabulary to borrow. */}
            <SectionNav className="hidden shrink-0 items-center gap-6 md:flex" />

            {/* The shell is reused by the public pages, so both halves of this
                row are conditional. Ticker search queries an authenticated
                endpoint — rendering it signed out would offer a control that
                401s on first keystroke. The spacer stays either way so the
                masthead keeps its rhythm. */}
            <div className="flex flex-1 justify-center px-2">
              {user && <TickerSearch />}
            </div>
            <div className="flex shrink-0 items-center gap-3">
              {/* Set in ink, not ink-3. Sign out is a quiet exit and belongs
                  in the grey; Contact is the way in for anyone who does not
                  have an account, so it reads as a nav item rather than as
                  chrome. Top-right is where people look for it. */}
              <Link
                to="/contact"
                className="px-2.5 py-2 text-[11px] font-bold uppercase tracking-[0.12em] text-ink outline-none transition-colors hover:bg-ink hover:text-bg focus-visible:ring-2 focus-visible:ring-accent"
              >
                Contact
              </Link>
              {user ? (
                <>
                  <span className="tnum hidden text-[11px] uppercase tracking-[0.1em] text-ink-3 sm:inline">
                    {user.display_name || user.email}
                  </span>
                  <button
                    onClick={logout}
                    className="flex items-center gap-1.5 px-2.5 py-2 text-[11px] font-bold uppercase tracking-[0.12em] text-ink-3 outline-none transition-colors hover:bg-ink hover:text-bg focus-visible:ring-2 focus-visible:ring-accent"
                  >
                    <SignOut size={14} weight="bold" /> Sign out
                  </button>
                </>
              ) : (
                <Link
                  to="/login"
                  className="px-2.5 py-2 text-[11px] font-bold uppercase tracking-[0.12em] text-ink-3 outline-none transition-colors hover:bg-ink hover:text-bg focus-visible:ring-2 focus-visible:ring-accent"
                >
                  Sign in
                </Link>
              )}
            </div>
          </div>
          <SectionNav className="flex items-center gap-6 overflow-x-auto border-t border-line py-2.5 md:hidden" />
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
        {/* "/" is the front door and is public. Until now it was the app
            behind a sign-in wall, so anyone following a link met a login form
            before they could find out what Arus is. */}
        <Route
          path="/" element={
            <Shell>
              <HomePage />
            </Shell>
          }
        />
        <Route
          path="/portfolios" element={
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
        {/* No RequireAuth: the people most likely to write in are the ones
            without an account. It still uses the shell, so the masthead and
            colophon are the same page furniture as everywhere else. */}
        <Route
          path="/contact" element={
            <Shell>
              <ContactPage />
            </Shell>
          }
        />
        {/* Public, like /contact: these are what someone reads BEFORE they
            have any reason to make an account. */}
        <Route
          path="/consulting" element={
            <Shell>
              <ConsultingPage />
            </Shell>
          }
        />
        <Route
          path="/research" element={
            <Shell>
              <ResearchPage />
            </Shell>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
