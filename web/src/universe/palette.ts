/** Newsprint stocks, one per franchise, assigned by franchise id order (cycled). */
export const FRANCHISE_STOCKS = [
  "#F6C9C2",
  "#F3E6A0",
  "#C9E6D2",
  "#C8DCEE",
  "#D9D0EE",
  "#F8D6B3",
  "#DCE3C3",
] as const;

/**
 * The deep shade each stock's score dots are printed in, same order as the stocks: the
 * tone keeps the franchise's hue instead of greying it, and stays a dot screen.
 */
export const FRANCHISE_INKS = [
  "#9E2A1C",
  "#946E00",
  "#1E7A3E",
  "#1D4F86",
  "#4B2A8C",
  "#A4520E",
  "#56740F",
] as const;

export const INK = "#121212";
export const PAPER = "#FFFFFF";
export const MASTHEAD_RED = "#E4002B";

/**
 * The stock of each franchise: sort the ids ascending, the first gets the first stock,
 * and so on, cycling after seven. Anime with no franchise print on plain paper.
 */
export function stockByFranchiseId(franchiseIds: readonly number[]): Map<number, string> {
  const sorted = [...new Set(franchiseIds)].sort((a, b) => a - b);
  return new Map(sorted.map((id, index) => [id, FRANCHISE_STOCKS[index % FRANCHISE_STOCKS.length]!]));
}

/** The dot colour for a stock: its deep shade, or ink for plain paper. */
export function toneInkFor(stock: string): string {
  const i = FRANCHISE_STOCKS.findIndex((s) => s.toLowerCase() === stock.toLowerCase());
  return i === -1 ? INK : FRANCHISE_INKS[i]!;
}
