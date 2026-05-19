/**
 * ThinAI — inline SVG icon set for game objects.
 *
 * Every icon is a function that accepts a fill colour string and returns
 * the SVG *inner* markup (meant to be dropped inside a
 * <svg viewBox="0 0 24 24" ...> wrapper).
 *
 * All paths target a 24x24 viewBox with simple geometry so they stay
 * readable at 20-30 px.
 */

export const icons = {
  // ── Pieces ────────────────────────────────────────────────────────

  stone: (color) =>
    `<circle cx="12" cy="12" r="10" fill="${color}"/>`,

  disc: (color) =>
    `<ellipse cx="12" cy="13" rx="10" ry="7" fill="${color}"/>` +
    `<ellipse cx="12" cy="11" rx="10" ry="7" fill="${color}" opacity="0.7"/>`,

  checker: (color) =>
    `<circle cx="12" cy="12" r="10" fill="${color}"/>` +
    `<circle cx="12" cy="12" r="6" fill="none" stroke="#fff" stroke-width="1.5"/>`,

  pawn: (color) =>
    `<circle cx="12" cy="6" r="4" fill="${color}"/>` +
    `<path d="M8 22h8l-1-8H9z" fill="${color}"/>`,

  rook: (color) =>
    `<path d="M6 22h12v-4H6zM7 18h10V10H7zM7 10h2V6h2v4h2V6h2v4h2V10" fill="${color}"/>`,

  knight: (color) =>
    `<path d="M7 22h10l-1-6 2-4-3-2 1-4-3 1-2-3-2 3-1 4 2 2z" fill="${color}"/>`,

  bishop: (color) =>
    `<path d="M12 2l-3 8 3 4 3-4z" fill="${color}"/>` +
    `<path d="M8 22h8l-1-8H9z" fill="${color}"/>`,

  queen: (color) =>
    `<path d="M4 20h16l-2-10-3 4-3-6-3 6-3-4z" fill="${color}"/>` +
    `<circle cx="12" cy="4" r="2" fill="${color}"/>`,

  king: (color) =>
    `<path d="M4 20h16l-2-10-3 4-3-6-3 6-3-4z" fill="${color}"/>` +
    `<line x1="12" y1="2" x2="12" y2="7" stroke="${color}" stroke-width="2"/>` +
    `<line x1="10" y1="4" x2="14" y2="4" stroke="${color}" stroke-width="2"/>`,

  meeple: (color) =>
    `<circle cx="12" cy="5" r="3" fill="${color}"/>` +
    `<path d="M4 22l3-9h10l3 9z" fill="${color}"/>`,

  token: (color) =>
    `<circle cx="12" cy="12" r="9" fill="${color}"/>` +
    `<circle cx="12" cy="12" r="5" fill="none" stroke="#fff" stroke-width="1"/>`,

  // ── Military ──────────────────────────────────────────────────────

  soldier: (color) =>
    `<circle cx="12" cy="5" r="3" fill="${color}"/>` +
    `<path d="M8 10h8v6H8z" fill="${color}"/>` +
    `<path d="M9 16h2v6H9zM13 16h2v6h-2z" fill="${color}"/>`,

  ship: (color) =>
    `<path d="M2 16l4 4h12l4-4z" fill="${color}"/>` +
    `<path d="M12 4v12" stroke="${color}" stroke-width="2"/>` +
    `<path d="M12 4l6 6h-6z" fill="${color}" opacity="0.7"/>`,

  flag: (color) =>
    `<line x1="6" y1="3" x2="6" y2="22" stroke="${color}" stroke-width="2"/>` +
    `<path d="M6 3h12l-3 5 3 5H6z" fill="${color}"/>`,

  shield: (color) =>
    `<path d="M12 2L4 6v6c0 5 3.5 9.7 8 11 4.5-1.3 8-6 8-11V6z" fill="${color}"/>`,

  sword: (color) =>
    `<line x1="12" y1="2" x2="12" y2="18" stroke="${color}" stroke-width="2.5"/>` +
    `<line x1="7" y1="14" x2="17" y2="14" stroke="${color}" stroke-width="2.5"/>` +
    `<rect x="11" y="18" width="2" height="4" fill="${color}"/>`,

  cannon: (color) =>
    `<rect x="4" y="14" width="12" height="4" rx="2" fill="${color}"/>` +
    `<circle cx="6" cy="20" r="2" fill="${color}"/>` +
    `<circle cx="14" cy="20" r="2" fill="${color}"/>` +
    `<rect x="14" y="12" width="6" height="4" rx="1" fill="${color}"/>`,

  // ── Symbols ───────────────────────────────────────────────────────

  star: (color) =>
    `<polygon points="12,2 15,9 22,9 16,14 18,22 12,17 6,22 8,14 2,9 9,9" fill="${color}"/>`,

  diamond: (color) =>
    `<polygon points="12,2 22,12 12,22 2,12" fill="${color}"/>`,

  heart: (color) =>
    `<path d="M12 21C8 17 2 13 2 8a5 5 0 0 1 10 0 5 5 0 0 1 10 0c0 5-6 9-10 13z" fill="${color}"/>`,

  cross: (color) =>
    `<rect x="9" y="2" width="6" height="20" rx="1" fill="${color}"/>` +
    `<rect x="2" y="9" width="20" height="6" rx="1" fill="${color}"/>`,

  triangle: (color) =>
    `<polygon points="12,3 22,21 2,21" fill="${color}"/>`,

  circle: (color) =>
    `<circle cx="12" cy="12" r="10" fill="none" stroke="${color}" stroke-width="2"/>`,

  square: (color) =>
    `<rect x="3" y="3" width="18" height="18" rx="2" fill="${color}"/>`,

  // ── Characters ────────────────────────────────────────────────────

  wizard: (color) =>
    `<polygon points="12,1 8,10 16,10" fill="${color}"/>` +
    `<circle cx="12" cy="13" r="4" fill="${color}"/>` +
    `<polygon points="6,17 12,14 18,17 16,23 8,23" fill="${color}"/>` +
    `<circle cx="12" cy="4" r="1.5" fill="${color}" opacity="0.5"/>`,

  dragon: (color) =>
    `<path d="M4,18 Q8,6 12,10 Q16,6 20,14 L18,18 Q14,14 12,16 Q10,14 6,18 Z" fill="${color}"/>` +
    `<polygon points="18,14 22,8 20,14" fill="${color}"/>` +
    `<circle cx="10" cy="11" r="1" fill="#000"/>`,

  ghost: (color) =>
    `<path d="M6,22 L6,10 Q6,3 12,3 Q18,3 18,10 L18,22 L16,19 L14,22 L12,19 L10,22 L8,19 Z" fill="${color}"/>` +
    `<circle cx="9" cy="10" r="2" fill="#000"/>` +
    `<circle cx="15" cy="10" r="2" fill="#000"/>`,

  pirate: (color) =>
    `<circle cx="12" cy="10" r="6" fill="${color}"/>` +
    `<rect x="5" y="7" width="14" height="3" rx="1" fill="${color}" opacity="0.7"/>` +
    `<polygon points="8,17 12,14 16,17 14,23 10,23" fill="${color}"/>` +
    `<line x1="8" y1="10" x2="16" y2="10" stroke="#000" stroke-width="1.5"/>`,

  ninja: (color) =>
    `<circle cx="12" cy="9" r="6" fill="${color}"/>` +
    `<rect x="5" y="7" width="14" height="4" fill="#222"/>` +
    `<polygon points="8,15 12,13 16,15 15,23 9,23" fill="${color}"/>`,

  wolf: (color) =>
    `<ellipse cx="12" cy="14" rx="7" ry="6" fill="${color}"/>` +
    `<polygon points="6,10 4,3 9,8" fill="${color}"/>` +
    `<polygon points="18,10 20,3 15,8" fill="${color}"/>` +
    `<circle cx="9" cy="12" r="1" fill="#000"/>` +
    `<circle cx="15" cy="12" r="1" fill="#000"/>`,

  bear: (color) =>
    `<circle cx="12" cy="13" r="8" fill="${color}"/>` +
    `<circle cx="6" cy="7" r="3" fill="${color}"/>` +
    `<circle cx="18" cy="7" r="3" fill="${color}"/>` +
    `<circle cx="10" cy="11" r="1.5" fill="#000"/>` +
    `<circle cx="14" cy="11" r="1.5" fill="#000"/>`,

  horse: (color) =>
    `<path d="M8,22 L8,14 Q6,8 10,4 L14,4 Q18,8 16,14 L16,22 Z" fill="${color}"/>` +
    `<polygon points="10,4 8,1 12,3" fill="${color}"/>` +
    `<circle cx="11" cy="7" r="1" fill="#000"/>`,

  // ── Resources ─────────────────────────────────────────────────────

  coin: (color) =>
    `<circle cx="12" cy="12" r="10" fill="${color}"/>` +
    `<text x="12" y="16" text-anchor="middle" font-size="12" fill="#fff" font-weight="bold">$</text>`,

  gem: (color) =>
    `<polygon points="12,2 20,9 16,22 8,22 4,9" fill="${color}"/>` +
    `<polyline points="4,9 12,12 20,9" fill="none" stroke="#fff" stroke-width="1" opacity="0.5"/>`,

  key: (color) =>
    `<circle cx="8" cy="8" r="4" fill="none" stroke="${color}" stroke-width="2"/>` +
    `<line x1="11" y1="11" x2="20" y2="20" stroke="${color}" stroke-width="2"/>` +
    `<line x1="17" y1="17" x2="20" y2="14" stroke="${color}" stroke-width="2"/>`,

  crown: (color) =>
    `<path d="M3 18h18l-2-10-4 4-3-6-3 6-4-4z" fill="${color}"/>` +
    `<rect x="3" y="18" width="18" height="3" rx="1" fill="${color}"/>`,

  trophy: (color) =>
    `<path d="M7 4h10v6a5 5 0 0 1-10 0z" fill="${color}"/>` +
    `<rect x="10" y="14" width="4" height="4" fill="${color}"/>` +
    `<rect x="7" y="18" width="10" height="3" rx="1" fill="${color}"/>` +
    `<path d="M7 4H3v4a3 3 0 0 0 3 3h1" fill="none" stroke="${color}" stroke-width="1.5"/>` +
    `<path d="M17 4h4v4a3 3 0 0 1-3 3h-1" fill="none" stroke="${color}" stroke-width="1.5"/>`,

  chest: (color) =>
    `<rect x="3" y="10" width="18" height="10" rx="2" fill="${color}"/>` +
    `<path d="M3 10h18v-3a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2z" fill="${color}" opacity="0.8"/>` +
    `<circle cx="12" cy="15" r="2" fill="#fff" opacity="0.5"/>`,

  potion: (color) =>
    `<path d="M9 2h6v4l3 10a3 3 0 0 1-3 3H9a3 3 0 0 1-3-3l3-10z" fill="${color}"/>` +
    `<rect x="9" y="2" width="6" height="3" rx="1" fill="${color}" opacity="0.7"/>`,

  scroll: (color) =>
    `<rect x="6" y="4" width="12" height="16" rx="1" fill="${color}"/>` +
    `<circle cx="6" cy="4" r="2" fill="${color}"/>` +
    `<circle cx="18" cy="4" r="2" fill="${color}"/>` +
    `<circle cx="6" cy="20" r="2" fill="${color}"/>` +
    `<circle cx="18" cy="20" r="2" fill="${color}"/>`,

  // ── Nature / Board ────────────────────────────────────────────────

  tree: (color) =>
    `<polygon points="12,2 20,14 16,14 20,20 4,20 8,14 4,14" fill="${color}"/>` +
    `<rect x="10" y="20" width="4" height="3" fill="#8B4513"/>`,

  mountain: (color) =>
    `<polygon points="2,22 12,4 22,22" fill="${color}"/>` +
    `<polygon points="8,22 14,12 20,22" fill="${color}" opacity="0.7"/>`,

  castle: (color) =>
    `<rect x="4" y="10" width="16" height="12" fill="${color}"/>` +
    `<rect x="4" y="6" width="4" height="4" fill="${color}"/>` +
    `<rect x="10" y="6" width="4" height="4" fill="${color}"/>` +
    `<rect x="16" y="6" width="4" height="4" fill="${color}"/>` +
    `<rect x="9" y="16" width="6" height="6" fill="#fff" opacity="0.3"/>`,

  tower: (color) =>
    `<rect x="8" y="6" width="8" height="16" fill="${color}"/>` +
    `<rect x="6" y="2" width="4" height="4" fill="${color}"/>` +
    `<rect x="14" y="2" width="4" height="4" fill="${color}"/>` +
    `<rect x="10" y="16" width="4" height="6" fill="#fff" opacity="0.3"/>`,

  house: (color) =>
    `<polygon points="12,3 22,13 2,13" fill="${color}"/>` +
    `<rect x="5" y="13" width="14" height="9" fill="${color}" opacity="0.85"/>` +
    `<rect x="10" y="16" width="4" height="6" fill="#fff" opacity="0.3"/>`,

  wall: (color) =>
    `<rect x="2" y="8" width="20" height="12" rx="1" fill="${color}"/>` +
    `<line x1="2" y1="14" x2="22" y2="14" stroke="#fff" stroke-width="0.5" opacity="0.4"/>` +
    `<line x1="8" y1="8" x2="8" y2="14" stroke="#fff" stroke-width="0.5" opacity="0.4"/>` +
    `<line x1="16" y1="8" x2="16" y2="14" stroke="#fff" stroke-width="0.5" opacity="0.4"/>` +
    `<line x1="12" y1="14" x2="12" y2="20" stroke="#fff" stroke-width="0.5" opacity="0.4"/>`,

  bridge: (color) =>
    `<path d="M2 12h20" stroke="${color}" stroke-width="3"/>` +
    `<path d="M4 12v6M20 12v6" stroke="${color}" stroke-width="2"/>` +
    `<path d="M4 18q8-8 16 0" fill="none" stroke="${color}" stroke-width="1.5"/>`,

  // ── Directional Arrows ────────────────────────────────────────────

  "arrow-up": (color) =>
    `<path d="M12 3l-7 8h4v10h6V11h4z" fill="${color}"/>`,

  "arrow-down": (color) =>
    `<path d="M12 21l7-8h-4V3h-6v10H5z" fill="${color}"/>`,

  "arrow-left": (color) =>
    `<path d="M3 12l8-7v4h10v6H11v4z" fill="${color}"/>`,

  "arrow-right": (color) =>
    `<path d="M21 12l-8 7v-4H3v-6h10V5z" fill="${color}"/>`,

  // ── Card ──────────────────────────────────────────────────────────

  card: (color) =>
    `<rect x="4" y="2" width="16" height="20" rx="2" fill="#fff" stroke="${color}" stroke-width="2"/>` +
    `<circle cx="12" cy="12" r="4" fill="${color}"/>`,
};

/**
 * Wrap icon SVG content in a full <svg> element string.
 *
 * @param {string} name   - Icon key (e.g. "pawn")
 * @param {string} color  - Fill colour (e.g. "#333", "red")
 * @param {number} [size] - Width/height in px (default 24)
 * @returns {string|null} Complete SVG string, or null if icon not found.
 */
export function renderIcon(name, color = "currentColor", size = 24) {
  const fn = icons[name];
  if (!fn) return null;
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"` +
    ` width="${size}" height="${size}">${fn(color)}</svg>`
  );
}

/**
 * List all available icon names.
 * @returns {string[]}
 */
export function availableIcons() {
  return Object.keys(icons);
}
