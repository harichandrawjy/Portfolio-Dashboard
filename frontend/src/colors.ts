/**
 * Chart colors. The 8 categorical slots are dataviz-validated against the
 * paper surface #f7f7f4 (lightness band, chroma floor, adjacent-pair CVD
 * separation >= 18.7 dE, contrast >= 3:1). Assign slots in fixed order,
 * never cycled; overflow folds into "Other" drawn in CHART_NEUTRAL.
 */

export const SERIES = [
  "#1d5bbf", // 1 cobalt (app accent — portfolio series)
  "#a16207", // 2 amber
  "#079e89", // 3 teal
  "#bd5b2e", // 4 terracotta
  "#7048b6", // 5 violet
  "#56750f", // 6 olive
  "#b23a7e", // 7 magenta
  "#2b7fb8", // 8 steel
] as const;

/** Benchmark line + "Other" fold slice. Deliberately reads as neutral. */
export const CHART_NEUTRAL = "#6b7280";

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
