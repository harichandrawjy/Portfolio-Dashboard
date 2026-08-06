import { X } from "@phosphor-icons/react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

/* ------------------------------------------------------------------ */
/* Surfaces                                                            */
/*                                                                     */
/* There are no cards in this system. A region is an area of the same  */
/* sheet, opened by a rule across its top edge — heavy for a major     */
/* block, hairline for a subordinate one. Nothing is raised, rounded,  */
/* or shadowed.                                                        */
/* ------------------------------------------------------------------ */

export function Panel({
  children,
  className = "",
  tone = "raised",
}: {
  children: ReactNode;
  className?: string;
  /** raised = major block, opened by a 3px near-black rule
   *  flat    = subordinate block, opened by a hairline */
  tone?: "raised" | "flat";
}) {
  const surface =
    tone === "raised"
      ? "bg-panel border-t-[3px] border-line-2"
      : "bg-transparent border-t border-line";
  return <section className={`${surface} ${className}`}>{children}</section>;
}

/**
 * The section caption. A Swiss plate caption rather than a heading: the
 * sequence number in accent, the title set small, bold, wide and uppercase.
 * Size contrast against the figures below is what creates the hierarchy —
 * the caption does not need to be big to be first.
 */
export function PanelHeader({
  seq,
  title,
  meta,
  right,
}: {
  /** two-digit section number, e.g. "02" — decorative, hidden from AT */
  seq?: string;
  title: string;
  meta?: string;
  right?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2 px-4 pb-3 pt-3 sm:px-5">
      <h2 className="flex items-baseline gap-3 text-[12px] font-bold uppercase leading-none tracking-[0.14em] text-ink">
        {seq && (
          <span className="seq text-accent" aria-hidden>
            {seq}
          </span>
        )}
        <span className="w-wide">{title}</span>
        {meta && (
          <span className="tnum text-[12px] font-medium tracking-normal text-ink-3 normal-case">
            {meta}
          </span>
        )}
      </h2>
      {right}
    </div>
  );
}

/**
 * A page-level numbered section head: the number, the title, and a rule
 * that draws itself across the full measure. This is the system's main
 * structural device — it is what makes the page read as a grid.
 */
export function SectionHead({
  seq,
  title,
  right,
  className = "",
}: {
  seq: string;
  title: string;
  right?: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        <h2 className="flex items-baseline gap-3 text-[12px] font-bold uppercase leading-none tracking-[0.14em] text-ink">
          <span className="seq text-accent" aria-hidden>
            {seq}
          </span>
          <span className="w-wide">{title}</span>
        </h2>
        {right}
      </div>
      <div className="rule-draw mt-2 h-px w-full bg-line-2" />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Colophon                                                            */
/* ------------------------------------------------------------------ */

/**
 * The page ends in a full-bleed field of the accent carrying an oversized
 * knockout wordmark. It exists because a short page left a large blank
 * region under the content with nothing to do; a flat colour field ends the
 * page deliberately instead of letting it trail off.
 *
 * It is a surface, not a decoration — it holds the data provenance and the
 * not-real-money disclaimer, which have to live somewhere anyway.
 *
 * Full-bleed is deliberate and the one sanctioned exception to the One
 * Measure Rule: the FIELD spans the viewport, but everything inside it stays
 * in the same 1200px measure as every other page. The wordmark is clipped by
 * `overflow-hidden` and sits on a negative bottom margin so it bleeds off the
 * bottom edge, which is what keeps it reading as a printed mark rather than
 * as very large text.
 */
export function Colophon() {
  return (
    <footer className="mt-24 overflow-hidden bg-accent text-on-accent">
      <div className="mx-auto max-w-[1200px] px-4">
        <dl className="flex flex-wrap gap-x-12 gap-y-6 pb-10 pt-10">
          {[
            ["963", "IDX tickers"],
            ["5y", "daily bars"],
            ["IHSG", "benchmark"],
            ["Delayed", "never real-time"],
          ].map(([v, l]) => (
            <div key={l}>
              <dt className="sr-only">{l}</dt>
              <dd className="tnum text-[19px] font-bold leading-none">{v}</dd>
              <dd className="w-wide mt-2 text-[10px] font-bold uppercase tracking-[0.14em] text-on-accent/70">
                {l}
              </dd>
            </div>
          ))}
        </dl>

        <p className="w-wide max-w-[52ch] border-t border-on-accent/25 pt-5 text-[11px] font-bold uppercase leading-relaxed tracking-[0.12em] text-on-accent/70">
          Mock portfolios only — no real money moves here
        </p>

        {/* the mark, cropped by the field's bottom edge */}
        <p
          aria-hidden
          className="w-condensed -mb-[0.14em] mt-6 select-none text-[clamp(4.5rem,19vw,15rem)] font-extrabold uppercase leading-[0.78] tracking-[-0.045em] text-on-accent"
        >
          Arus
        </p>
      </div>
    </footer>
  );
}

/* ------------------------------------------------------------------ */
/* Buttons                                                             */
/*                                                                     */
/* Square, flat, uppercase and letterspaced — a pressed label rather    */
/* than a soft chip. The ghost inverts to solid ink on hover, which is  */
/* the system's standard "this is interactive" answer.                  */
/* ------------------------------------------------------------------ */

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  /** `buy`/`sell` are the order-entry commit buttons and the only buttons
   *  allowed to carry a signal colour — they exist so the side chosen in the
   *  toggle is restated by the control that commits it. They are deliberately
   *  separate from `dangerSolid`, which keeps its own meaning (a confirmed
   *  destructive step); a sell is not a destructive action. */
  variant?:
    | "primary"
    | "ghost"
    | "danger"
    | "dangerSolid"
    | "text"
    | "buy"
    | "sell";
  busy?: boolean;
};

export function Button({
  variant = "primary",
  busy = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const base =
    // taller on a phone, where this is a thumb target rather than a cursor one
    "inline-flex items-center justify-center gap-2 px-4 py-3 sm:py-2.5 " +
    "text-[11px] font-bold uppercase tracking-[0.12em] leading-none " +
    // `press` carries both layers of press feedback — see styles.css. The
    // `active:` colours below are what acknowledge a tap on touch, where
    // there is no hover state to have already fired.
    "press outline-none " +
    "focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg " +
    "disabled:opacity-40 disabled:pointer-events-none whitespace-nowrap";
  const variants = {
    primary: "bg-accent text-on-accent hover:bg-accent-hover active:bg-accent-hover",
    ghost:
      "bg-transparent text-ink ring-1 ring-line-2 hover:bg-ink hover:text-bg active:bg-ink active:text-bg",
    danger:
      "bg-transparent text-neg ring-1 ring-neg hover:bg-neg hover:text-white active:bg-neg active:text-white",
    dangerSolid: "bg-neg text-white hover:bg-neg-hover active:bg-neg-hover",
    text: "px-2 text-ink-2 hover:text-ink hover:bg-panel-2 active:bg-panel-2 active:text-ink",
    buy: "bg-pos text-white hover:bg-pos-hover active:bg-pos-hover",
    sell: "bg-neg text-white hover:bg-neg-hover active:bg-neg-hover",
  };
  return (
    <button
      className={`${base} ${variants[variant]} ${className}`}
      disabled={disabled || busy}
      {...rest}
    >
      {busy ? "Working…" : children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Form field                                                          */
/*                                                                     */
/* A filled grey square with no resting border. Borders on every field  */
/* would out-shout the structural rules that carry the page, so the     */
/* field states itself by fill and only draws an edge when focused.     */
/* ------------------------------------------------------------------ */

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string | null;
};

export function Field({ label, hint, error, className = "", ...rest }: FieldProps) {
  return (
    <label className="flex flex-col gap-2">
      <span className="w-wide text-[11px] font-bold uppercase tracking-[0.12em] text-ink-2">
        {label}
      </span>
      <input
        className={
          "bg-panel-2 px-3 py-2.5 text-[13px] text-ink ring-1 ring-transparent " +
          "placeholder:text-ink-3 outline-none transition-shadow " +
          "focus:bg-panel focus:ring-2 focus:ring-accent " +
          className
        }
        {...rest}
      />
      {hint && !error && <span className="text-xs text-ink-3">{hint}</span>}
      {error && <span className="text-xs font-medium text-neg">{error}</span>}
    </label>
  );
}

/* ------------------------------------------------------------------ */
/* Segmented control (range switcher)                                  */
/*                                                                     */
/* The selected segment inverts to solid ink. No sliding pill, no       */
/* shadow — the state change is a hard colour flip.                     */
/* ------------------------------------------------------------------ */

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  /** names the group for assistive tech — several can share a toolbar */
  label?: string;
}) {
  return (
    <div
      role="radiogroup" aria-label={label}
      className="inline-flex bg-panel-2 p-0.5"
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button" role="radio" aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={
            "px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.1em] leading-none " +
            "outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent " +
            (o.value === value
              ? "bg-ink text-bg"
              : "text-ink-3 hover:text-ink")
          }
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Binary choice (Buy/Sell, Deposit/Withdraw)                          */
/* ------------------------------------------------------------------ */

/** The tone a selected side is filled with. `accent` is the default and the
 *  right answer nearly everywhere. `pos`/`neg` exist ONLY for the buy/sell
 *  side control — see "The Order-Entry Exception" in DESIGN.md. Do not reach
 *  for them to make an ordinary toggle more colourful. */
type ToggleTone = "accent" | "pos" | "neg";

const TOGGLE_ON: Record<ToggleTone, string> = {
  accent: "bg-accent text-on-accent",
  pos: "bg-pos text-white",
  neg: "bg-neg text-white",
};

/** The chosen side is a flat filled field, accent by default — a withdrawal
 *  is not an error and cash movement is not a signed value, so the cash modal
 *  keeps the default deliberately. Only the order modals pass `pos`/`neg`,
 *  where the broker convention is load-bearing against mis-recording a trade
 *  and no signed figure shares the surface. */
export function BinaryToggle<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string; tone?: ToggleTone }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="grid grid-cols-2 gap-px bg-line">
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button" role="radio" aria-checked={on}
            onClick={() => onChange(o.value)}
            className={
              "py-2.5 text-[11px] font-bold uppercase tracking-[0.12em] leading-none " +
              "outline-none transition-colors " +
              "focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-panel " +
              (on
                ? TOGGLE_ON[o.tone ?? "accent"]
                : "bg-panel-2 text-ink-3 hover:text-ink")
            }
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Toasts — confirmation for ledger writes                             */
/* ------------------------------------------------------------------ */

interface Toast {
  id: number;
  message: string;
  /** set while the exit animation plays, just before the toast unmounts */
  exiting?: boolean;
}

const ToastContext = createContext<((message: string) => void) | null>(null);

/**
 * Recording, editing and deleting all mutate a ledger that holdings and cash
 * are derived from, so each one needs to say it happened. A toast confirms
 * without holding the dialog open — the dialog closing is still the signal
 * that the task is done.
 *
 * The container is always mounted so it is a live region from the start;
 * a region created at announce-time is not reliably read out.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<number[]>([]);

  /** Marks the toast as leaving, lets it animate out, then unmounts it. The
   *  two-step matters because a toast that eased in and then vanished on a
   *  single frame read as a glitch rather than a dismissal. Flagging is
   *  idempotent, so the auto-dismiss timer firing on an already-dismissed
   *  toast cannot queue a second removal. */
  const dismiss = useCallback((id: number) => {
    let alreadyLeaving = false;
    setToasts((list) =>
      list.map((t) => {
        if (t.id !== id) return t;
        alreadyLeaving = t.exiting === true;
        return { ...t, exiting: true };
      }),
    );
    if (alreadyLeaving) return;
    timers.current.push(
      window.setTimeout(
        () => setToasts((list) => list.filter((t) => t.id !== id)),
        150,
      ),
    );
  }, []);

  const show = useCallback(
    (message: string) => {
      const id = Date.now() + Math.random();
      setToasts((list) => [...list, { id, message }]);
      timers.current.push(window.setTimeout(() => dismiss(id), 5000));
    },
    [dismiss],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      {createPortal(
        <div
          role="status" className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 p-4"
        >
          {toasts.map((t) => (
            <div
              key={t.id}
              className={`${t.exiting ? "toast-exit" : "toast-enter"} pointer-events-auto flex w-full max-w-[min(30rem,100%)] items-start gap-3 bg-ink px-4 py-3 text-[13px] leading-relaxed text-bg`}
            >
              {/* a solid accent mark, never a green tick: green means the sign
                  of a value in this system */}
              <span
                aria-hidden
                className="mt-[5px] block h-2 w-2 shrink-0 bg-accent"
              />
              <span className="flex-1">{t.message}</span>
              <button
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss" className="-m-1 shrink-0 p-1 text-bg/60 outline-none transition-colors hover:text-bg focus-visible:ring-2 focus-visible:ring-accent"
              >
                <X size={13} weight="bold" />
              </button>
            </div>
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): (message: string) => void {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast outside ToastProvider");
  return ctx;
}

/* ------------------------------------------------------------------ */
/* Inline explanation                                                  */
/* ------------------------------------------------------------------ */

/** A one-line plain-language gloss for a metric that assumes finance
 *  knowledge. A text toggle rather than a `?` bubble: it says what it does,
 *  needs no tooltip positioning, and is a real target at any size. */
export function WhatIsThis({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button" aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="-my-1 py-1 text-[11px] font-bold uppercase tracking-[0.1em] text-ink-3 underline decoration-line-2 underline-offset-4 outline-none transition-colors hover:text-ink focus-visible:ring-2 focus-visible:ring-accent"
      >
        {open ? "Hide" : "What these mean"}
        <span className="sr-only"> — {label}</span>
      </button>
      {open && (
        <p className="mt-2 max-w-[62ch] border-l-2 border-accent pl-3 text-xs leading-relaxed text-ink-2">
          {children}
        </p>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Skeleton & states                                                   */
/* ------------------------------------------------------------------ */

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

/** Left-aligned and typographic rather than a centred icon well: an empty
 *  region is still part of the grid, so it keeps the grid's alignment. */
export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon?: ReactNode;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-3 px-4 py-12 sm:px-5">
      {icon && <div className="text-accent">{icon}</div>}
      <p className="w-wide text-[13px] font-bold uppercase tracking-[0.12em] text-ink">
        {title}
      </p>
      <p className="max-w-[46ch] text-[13px] leading-relaxed text-ink-2">{body}</p>
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div
      role="alert" className="border-l-[3px] border-neg bg-neg/[0.07] px-3 py-2 text-[13px] font-medium text-neg"
    >
      {message}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Modal                                                               */
/* ------------------------------------------------------------------ */

export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Captured during the first render, which is the last moment the trigger
  // still holds focus: a child's autoFocus runs its effect before this
  // component's, so reading activeElement in the effect would return the
  // field inside the dialog and focus would land on <body> at close.
  const [restoreTo] = useState<Element | null>(() => document.activeElement);

  // The dialog owns its own dismissal so it can animate out. Callers still
  // just unmount it on `onClose`; this holds that off for the length of the
  // exit. Without it the sheet eased in over 220ms and then disappeared in a
  // single frame, which was the harshest transition in the app.
  const [closing, setClosing] = useState(false);
  const closeTimer = useRef<number | undefined>(undefined);
  const requestClose = useCallback(() => {
    // guard re-entry: Escape, the scrim and the X can all fire in one gesture,
    // and a second call would queue a second unmount
    if (closeTimer.current !== undefined) return;
    // honour the motion preference — no reason to delay an unmount for an
    // animation that is not going to run
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (still) {
      onClose();
      return;
    }
    setClosing(true);
    closeTimer.current = window.setTimeout(onClose, 150);
  }, [onClose]);

  useEffect(() => () => window.clearTimeout(closeTimer.current), []);

  // A dialog owns the keyboard while it is open: focus moves in on mount,
  // Tab cycles inside it, and the trigger gets focus back on close.
  useEffect(() => {
    const panel = panelRef.current;
    // A child's autoFocus has already run by now; only take focus if nothing
    // inside the dialog claimed it.
    if (panel && !panel.contains(document.activeElement)) panel.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        requestClose();
        return;
      }
      if (e.key !== "Tab" || !panel) return;
      const focusable = Array.from(
        panel.querySelectorAll<HTMLElement>(
          'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => el.offsetParent !== null);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (
        e.shiftKey &&
        (document.activeElement === first || document.activeElement === panel)
      ) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      // the trigger can be gone (a deleted row's button); skip it if so
      if (restoreTo instanceof HTMLElement && document.contains(restoreTo))
        restoreTo.focus();
    };
  }, [onClose, restoreTo]);

  // Portal to <body> so no ancestor's transform/overflow can trap the
  // fixed overlay inside a panel (the .rise entry animation uses transform).
  return createPortal(
    <div
      className={`${closing ? "overlay-exit" : "overlay-enter"} fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-ink/50 p-4 pt-[8vh]`}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) requestClose();
      }}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`${closing ? "modal-exit" : "modal-enter"} w-full ${wide ? "max-w-2xl" : "max-w-md"} bg-panel outline-none ring-1 ring-ink`}
        role="dialog" aria-modal="true" aria-label={title}
      >
        {/* the dialog states itself with an inverted ink bar, the one place
            the system uses a solid black field as a header */}
        <div className="flex items-center justify-between gap-3 bg-ink px-4 py-3 sm:px-5">
          <h2 className="w-wide text-[12px] font-bold uppercase tracking-[0.14em] text-bg">
            {title}
          </h2>
          <button
            onClick={requestClose}
            className="-mr-1 p-1.5 text-bg/60 outline-none transition-colors hover:text-bg focus-visible:ring-2 focus-visible:ring-accent sm:p-1" aria-label="Close"
          >
            <X size={16} weight="bold" />
          </button>
        </div>
        <div className="px-4 py-4 sm:px-5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

/* ------------------------------------------------------------------ */
/* Confirm dialog                                                      */
/* ------------------------------------------------------------------ */

export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  onConfirm,
  onClose,
  busy = false,
  error,
  danger = false,
}: {
  title: string;
  body: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  busy?: boolean;
  error?: string | null;
  danger?: boolean;
}) {
  return (
    <Modal title={title} onClose={onClose}>
      <div className="flex flex-col gap-4">
        <div className="text-[13px] leading-relaxed text-ink-2">{body}</div>
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant={danger ? "dangerSolid" : "primary"}
            onClick={onConfirm}
            busy={busy}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
