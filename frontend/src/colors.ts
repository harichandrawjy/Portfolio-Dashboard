/**
 * Chart colors. The 8 categorical slots are dataviz-validated against the
 * panel surface #11151d (lightness band, chroma floor, adjacent-pair CVD
 * separation >= 13.8 dE, contrast >= 3:1). Assign slots in fixed order,
 * never cycled; overflow folds into "Other" drawn in CHART_NEUTRAL.
 */

export const SERIES = [
  "#3987e5", // 1 blue (app accent — portfolio series)
  "#b98729", // 2 amber
  "#2aa396", // 3 teal
  "#cc7052", // 4 terracotta
  "#9a6fd6", // 5 lavender
  "#86932c", // 6 olive
  "#cf6699", // 7 pink
  "#4494c2", // 8 sky
] as const;

/** Benchmark line + "Other" fold slice. Deliberately reads as neutral. */
export const CHART_NEUTRAL = "#7f8ea3";

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
