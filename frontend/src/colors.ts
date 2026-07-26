/**
 * Chart colors, tuned to sit inside the cool porcelain + indigo system
 * rather than fight it. The early slots are a cohesive cool family
 * (indigo → teal → blue → periwinkle), so a typical few-sector donut
 * reads as one designed set; warmer accents only appear once a portfolio
 * spreads across many sectors. Slots are assigned in fixed order, never
 * cycled; overflow folds into "Other" drawn in CHART_NEUTRAL.
 */

export const SERIES = [
  "#2b3570", // 1 ink-indigo (app accent — the current / portfolio series)
  "#2f8f86", // 2 teal
  "#4f80b8", // 3 cornflower blue
  "#6f5fa8", // 4 periwinkle
  "#c08a3e", // 5 muted gold
  "#b0603c", // 6 terracotta
  "#a95a7e", // 7 dusty rose
  "#6f8a44", // 8 olive
] as const;

/** Benchmark line + "Other" fold slice. Deliberately reads as neutral. */
export const CHART_NEUTRAL = "#7a8397";

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
