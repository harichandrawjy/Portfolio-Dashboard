/**
 * One-click entry into the demo, wherever it is offered.
 *
 * WHY THIS IS A BUTTON AND NOT A LINK TO /portfolios. That route sits behind
 * `RequireAuth`, so a link would bounce a signed-out visitor to the sign-in
 * page — which is precisely the wall the demo exists to remove. Someone who
 * followed a "try the demo" promise and landed on a login form has been told
 * the opposite of what they were promised. This mints the account and goes
 * straight in.
 *
 * WHY IT IS SHARED. The rules around the demo are small but easy to get
 * subtly wrong, and there are now two places that offer it (the login panel
 * and the home page's hero). A second copy would be free to drift: a
 * deployment with `DEMO_ENABLED=false` answers 404, and a caller that forgot
 * to handle that ships a button which can only ever error. One
 * implementation, so the 404 rule and the busy state cannot disagree with
 * themselves.
 *
 * Renders NOTHING once the server has said 404 — an offer that cannot be
 * honoured is worse than no offer.
 */

import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth";
import { Button } from "./ui";

export function DemoButton({
  variant = "ghost",
  className = "",
  children = "Explore the demo portfolio",
  onError,
}: {
  variant?: "primary" | "ghost" | "onAccent" | "onAccentGhost";
  className?: string;
  children?: ReactNode;
  /** Lets a caller that already renders errors (the login panel) keep doing
   *  so. Without one the failure is reported inline, because a button that
   *  silently does nothing is the worst of the options. */
  onError?: (message: string) => void;
}) {
  const { user, demoLogin } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [offered, setOffered] = useState(true);
  const [error, setError] = useState<string | null>(null);

  if (!offered) return null;

  const launch = async () => {
    // Already signed in: take them to their own portfolios rather than
    // minting a demo over the top of a real session. Nobody clicking this
    // means "sign me out of my account".
    if (user) {
      navigate("/portfolios");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await demoLogin();
      navigate("/portfolios", { replace: true });
    } catch (err) {
      // 404 is not a failure to report — it is this deployment saying it does
      // not do demo sign-in. Retire the button rather than leaving one that
      // can only ever error.
      if (err instanceof ApiError && err.status === 404) {
        setOffered(false);
        return;
      }
      const message = (err as Error).message;
      if (onError) onError(message);
      else setError(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button
        variant={variant}
        className={className}
        busy={busy}
        onClick={launch}
      >
        {children}
      </Button>
      {error && !onError && (
        <p role="alert" className="mt-2 text-[13px] leading-relaxed text-neg">
          {error}
        </p>
      )}
    </>
  );
}
