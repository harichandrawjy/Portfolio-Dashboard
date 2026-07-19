import { X } from "@phosphor-icons/react";
import {
  useEffect,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

/* ------------------------------------------------------------------ */
/* Surfaces — a white sheet for primary content, a thick ink rule      */
/* opening each secondary section, like a printed report               */
/* ------------------------------------------------------------------ */

export function Panel({
  children,
  className = "",
  tone = "raised",
}: {
  children: ReactNode;
  className?: string;
  /** raised = white sheet card; flat = ruled editorial section on paper */
  tone?: "raised" | "flat";
}) {
  const surface =
    tone === "raised"
      ? "rounded-xl bg-panel ring-1 ring-line " +
        "shadow-[0_1px_2px_rgb(22_24_29/0.04),0_16px_40px_-28px_rgb(22_24_29/0.25)]"
      : "rounded-none border-t-2 border-ink bg-transparent";
  return <section className={`${surface} ${className}`}>{children}</section>;
}

export function PanelHeader({
  title,
  meta,
  right,
}: {
  title: string;
  meta?: string;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 px-5 pt-4 pb-3">
      <h2 className="text-[15px] font-semibold tracking-tight text-ink">
        {title}
        {meta && (
          <span className="tnum ml-2 font-mono text-xs font-normal text-ink-3">
            {meta}
          </span>
        )}
      </h2>
      {right}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Buttons — ink-filled primary, like a stamp                          */
/* ------------------------------------------------------------------ */

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger" | "text";
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
    "inline-flex items-center justify-center gap-2 rounded-[6px] px-4 py-2 text-sm font-medium " +
    "transition-all duration-200 ease-[cubic-bezier(0.32,0.72,0,1)] active:scale-[0.98] " +
    "outline-none focus-visible:ring-2 focus-visible:ring-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-bg " +
    "disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap";
  const variants = {
    primary:
      "bg-ink text-bg hover:bg-[#2b303a] shadow-[0_2px_6px_-2px_rgb(22_24_29/0.4)]",
    ghost: "bg-transparent text-ink ring-1 ring-line-2 hover:bg-ink/5",
    danger: "bg-transparent text-neg ring-1 ring-neg/40 hover:bg-neg/10",
    text: "px-2 text-ink-2 hover:text-ink hover:bg-ink/5",
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
/* ------------------------------------------------------------------ */

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string | null;
};

export function Field({ label, hint, error, className = "", ...rest }: FieldProps) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-[13px] font-medium text-ink-2">{label}</span>
      <input
        className={
          "rounded-[6px] bg-panel px-3 py-2 text-sm text-ink ring-1 ring-line " +
          "placeholder:text-ink-3 outline-none transition-shadow " +
          "focus:ring-2 focus:ring-accent/60 " +
          className
        }
        {...rest}
      />
      {hint && !error && <span className="text-xs text-ink-3">{hint}</span>}
      {error && <span className="text-xs text-neg">{error}</span>}
    </label>
  );
}

/* ------------------------------------------------------------------ */
/* Segmented control (range switcher)                                  */
/* ------------------------------------------------------------------ */

export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-[8px] bg-ink/[0.06] p-1 ring-1 ring-line">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={
            "rounded-[5px] px-3 py-1 text-xs font-medium outline-none transition-colors duration-200 " +
            "focus-visible:ring-2 focus-visible:ring-accent/70 " +
            (o.value === value
              ? "bg-panel text-ink shadow-[0_1px_2px_rgb(22_24_29/0.12)] ring-1 ring-line"
              : "text-ink-3 hover:text-ink-2")
          }
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Skeleton & states                                                   */
/* ------------------------------------------------------------------ */

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

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
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      {icon && <div className="text-ink-3">{icon}</div>}
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="max-w-[38ch] text-[13px] leading-relaxed text-ink-3">{body}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-[6px] bg-neg/10 px-3 py-2 text-[13px] text-neg ring-1 ring-neg/25">
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
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-ink/25 p-4 pt-[10vh]"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={`modal-enter w-full ${wide ? "max-w-lg" : "max-w-md"} rounded-xl bg-panel ring-1 ring-line shadow-[0_32px_80px_-24px_rgb(22_24_29/0.4)]`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-[5px] p-1 text-ink-3 outline-none transition-colors hover:bg-ink/5 hover:text-ink focus-visible:ring-2 focus-visible:ring-accent/70"
            aria-label="Close"
          >
            <X size={16} weight="light" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}
