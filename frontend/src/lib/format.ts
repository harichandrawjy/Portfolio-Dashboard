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

export function fmtPct(n: number | null | undefined, signed = false): string {
  if (n == null) return DASH;
  const s = n.toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return (signed && n > 0 ? "+" : "") + s + "%";
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

/** Tailwind text class for a positive/negative amount. */
export function signClass(n: number | null | undefined): string {
  if (n == null || n === 0) return "text-ink-2";
  return n > 0 ? "text-pos" : "text-neg";
}
