/**
 * Where an emailed link lands: `/verify?token=…` and `/reset?token=…`.
 *
 * One file for both because they are the same screen with a different verb —
 * a token out of the query string, one call, and either a session or a reason
 * it failed. Splitting them duplicated the layout, the token-missing branch
 * and the error handling three ways.
 *
 * Neither page is reachable from anywhere in the app, which is the point: the
 * only way in is a link from a mailbox, and that is what makes following one
 * evidence of controlling the address.
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { useAuth } from "../auth";
import { Button, ErrorNote, Field } from "../components/ui";

/** The brand half of the login screen, reused so a link does not land the
 *  visitor somewhere that looks like a different product. */
function Shell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid min-h-[100dvh] lg:grid-cols-[1.15fr_1fr]">
      <aside className="field-wipe relative flex flex-col justify-between gap-10 overflow-hidden bg-accent px-6 py-8 text-on-accent lg:gap-0 lg:p-12">
        <p className="w-wide relative flex items-baseline gap-1.5 text-[19px] font-extrabold uppercase leading-none tracking-[0.16em]">
          Arus
          <span aria-hidden className="block h-2 w-2 bg-on-accent" />
        </p>
        <div className="relative">
          <div className="rule-draw mb-6 h-[3px] w-24 bg-on-accent lg:mb-10" />
          <h1 className="w-condensed text-[clamp(2.75rem,7vw,5.5rem)] font-extrabold uppercase leading-[0.88] tracking-[-0.03em]">
            {title}
          </h1>
        </div>
      </aside>
      <main className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">{children}</div>
      </main>
    </div>
  );
}

export function VerifyPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const navigate = useNavigate();
  const { adoptToken } = useAuth();
  const [error, setError] = useState<string | null>(null);
  // React 18 mounts effects twice in development. Without this the second run
  // redeems an already-redeemed token and the page reports a valid link as
  // expired — the failure looks exactly like the real one it is meant to show.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (!token) {
      setError("That link is missing its token. Open the most recent email.");
      return;
    }
    api.confirmEmail(token).then(
      async ({ access_token }) => {
        await adoptToken(access_token);
        navigate("/", { replace: true });
      },
      (e: unknown) =>
        setError(
          e instanceof ApiError
            ? e.message
            : "Could not reach the server. Try the link again.",
        ),
    );
  }, [token, adoptToken, navigate]);

  return (
    <Shell title={error ? "Link expired" : "Confirming"}>
      {error ? (
        <>
          <ErrorNote message={error} />
          <p className="mt-5 text-[13px] leading-relaxed text-ink-3">
            Verification links work once and expire after 24 hours. Sign in to
            have a new one sent.
          </p>
          <Button className="mt-5 w-full" onClick={() => navigate("/login")}>
            Back to sign in
          </Button>
        </>
      ) : (
        <p className="text-[13px] text-ink-3">Confirming your address…</p>
      )}
    </Shell>
  );
}

export function ResetPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const navigate = useNavigate();
  const { adoptToken } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Checked here as well as by the field's own minLength so the message is the
  // same one the server would give, rather than a browser tooltip.
  const tooShort = password.length > 0 && password.length < 8;
  const mismatch = confirm.length > 0 && confirm !== password;
  const canSubmit =
    !!token && password.length >= 8 && confirm === password && !busy;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit || !token) return;
    setBusy(true);
    setError(null);
    try {
      const { access_token } = await api.resetPassword(token, password);
      await adoptToken(access_token);
      navigate("/", { replace: true });
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Could not reach the server. Try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <Shell title="Link expired">
        <ErrorNote message="That link is missing its token. Open the most recent email." />
        <Button className="mt-5 w-full" onClick={() => navigate("/login")}>
          Back to sign in
        </Button>
      </Shell>
    );
  }

  return (
    <Shell title="New password">
      <form onSubmit={submit} className="flex flex-col gap-4">
        {error && <ErrorNote message={error} />}
        <Field
          label="New password" type="password" value={password}
          onChange={(e) => setPassword(e.target.value)}
          hint="At least 8 characters"
          error={tooShort ? "At least 8 characters" : undefined}
          autoFocus
        />
        <Field
          label="Confirm password" type="password" value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={mismatch ? "The two do not match" : undefined}
        />
        <Button type="submit" busy={busy} disabled={!canSubmit} className="mt-2 w-full">
          Set password
        </Button>
      </form>
      <p className="mt-5 text-[13px] leading-relaxed text-ink-3">
        Setting a new password signs out every device currently on the account.
      </p>
    </Shell>
  );
}
