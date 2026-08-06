/** Formatting helpers. All rupiah amounts arrive as whole-number integers. */

const rp = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  maximumFractionDigits: 0,
});

const rpCompact = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  notation: "compact",
  maximumFractionDigits: 1,
});

const num = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 });

const dateShort = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
});

const dateFull = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

const timeWib = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Jakarta",
});

/** Missing data renders as an em-dash placeholder, never as 0 or a crash. */
export const DASH = "—";

export function fmtRp(n: number | null | undefined): string {
  return n == null ? DASH : rp.format(n);
}

export function fmtRpCompact(n: number): string {
  return rpCompact.format(n);
}

export function fmtNum(n: number | null | undefined): string {
  return n == null ? DASH : num.format(n);
}

const numCompact = new Intl.NumberFormat("id-ID", {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** Plain compact count, e.g. share volume: 256,7 jt */
export function fmtNumCompact(n: number | null | undefined): string {
  return n == null ? DASH : numCompact.format(n);
}

export function fmtPct(n: number | null | undefined, signed = false): string {
  if (n == null) return DASH;
  const s = n.toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return (signed && n > 0 ? "+" : "") + s + "%";
}

/**
 * Ratios, multiples, betas and scores. Everything else on screen is formatted
 * id-ID, so a raw `toFixed` puts "1.25×" next to "Rp 27.742.500" and "-3,93%"
 * and the locale visibly breaks. Route every user-facing decimal through here.
 */
export function fmtDec(n: number | null | undefined, digits = 2): string {
  if (n == null) return DASH;
  return n.toLocaleString("id-ID", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtSignedRp(n: number | null | undefined): string {
  if (n == null) return DASH;
  return (n > 0 ? "+" : "") + rp.format(n);
}

export function fmtDate(iso: string): string {
  return dateFull.format(new Date(iso));
}

export function fmtDateShort(iso: string): string {
  return dateShort.format(new Date(iso));
}

/** Quote timestamps display in WIB because that is IDX's clock. */
export function fmtAsOf(iso: string | null | undefined): string {
  return iso == null ? DASH : timeWib.format(new Date(iso)) + " WIB";
}

/** Strip everything but digits (for controlled numeric text inputs). */
export function digitsOnly(s: string): string {
  return s.replace(/\D/g, "");
}

/** Group digits with id-ID thousands dots while typing: 10000000 -> 10.000.000 */
export function groupDigits(s: string): string {
  return digitsOnly(s).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/** Tailwind text class for a positive/negative amount. */
export function signClass(n: number | null | undefined): string {
  if (n == null || n === 0) return "text-ink-2";
  return n > 0 ? "text-pos" : "text-neg";
}
