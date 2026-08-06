/**
 * Chart colors for the Raster system. Slot 1 is always the app accent, so
 * the portfolio's own series is the same colour as the interface around it.
 * Slots are assigned in fixed sector order, never cycled; overflow folds
 * into "Other" drawn in CHART_NEUTRAL.
 *
 * Values are darkened relative to the previous porcelain-ground system:
 * these sit on pure white next to near-black ink, so a mid-tone that read
 * fine on #edeff4 reads washed out here.
 *
 * WHY SEVEN AND NOT EIGHT. Three hues are unavailable to this palette —
 * green, red and amber mean the sign of a value and nothing else — and the
 * deep-sea accent now occupies the blue region as well. Every candidate
 * eighth slot was measured with CIEDE2000 against the other seven, the
 * benchmark grey, and the two signal colours; all of them landed under
 * ΔE 15 on some pair (deep teal 15 vs the gain green, umber 13 vs
 * terracotta, steel 11 and slate 14 vs the accent itself, pink 10 vs rose).
 * Seven is the honest ceiling, so the eighth sector folds into "Other"
 * rather than shipping two slices nobody can tell apart.
 *
 * Known residual tension, unchanged from the previous palette: terracotta
 * sits ΔE 13 from the loss red and olive ΔE 13 from the gain green. Both are
 * late slots that only appear in wide portfolios, and the signal colours
 * appear as *text* while these appear as labelled *fills*, so the two never
 * compete in the same role. Retune these before adding any new series.
 *
 * If you change the accent, re-measure this whole set — slot 1 moves with it.
 */

/**
 * Read a design token off :root. Canvas and SVG renderers (Lightweight
 * Charts, Recharts) need literal colour strings and cannot use Tailwind
 * classes — without this they drift into hardcoded near-duplicates of the
 * real tokens. Call it at render/effect time, never at module scope.
 */
export function token(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(`--color-${name}`)
    .trim();
  return v || fallback;
}

export const SERIES = [
  "#084d77", // 1 deep sea (app accent — always the portfolio's own series)
  "#8a4fb8", // 2 violet
  "#b07a20", // 3 gold
  "#a34a28", // 4 terracotta
  "#7bb2d9", // 5 sky — separated from slot 1 by lightness, not hue
  "#99486e", // 6 dusty rose
  "#4f7a2f", // 7 olive
] as const;

/** Benchmark line + "Other" fold slice. Deliberately reads as neutral. */
export const CHART_NEUTRAL = "#767d8c";

/** Canonical IDX-IC sector order so a sector keeps its color everywhere. */
const SECTOR_ORDER = [
  "Keuangan",
  "Energi",
  "Barang Baku",
  "Perindustrian",
  "Barang Konsumen Primer",
  "Barang Konsumen Non-Primer",
  "Kesehatan",
  "Properti & Real Estat",
  "Teknologi",
  "Infrastruktur",
  "Transportasi & Logistik",
];

export function sectorColor(sector: string | null, held: (string | null)[]): string {
  if (sector === null) return CHART_NEUTRAL;
  // Stable assignment: order the held sectors canonically, then hand out
  // slots in that order. Colors follow the sector, not its weight rank.
  const canonical = held
    .filter((s): s is string => s !== null)
    .sort((a, b) => {
      const ia = SECTOR_ORDER.indexOf(a);
      const ib = SECTOR_ORDER.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });
  const idx = canonical.indexOf(sector);
  if (idx === -1 || idx >= SERIES.length) return CHART_NEUTRAL;
  return SERIES[idx];
}
