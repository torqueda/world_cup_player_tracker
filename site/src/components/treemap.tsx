export interface TreemapItem {
  key: string;
  label: string;
  value: number;
  /** Optional hover text; defaults to "label: value". */
  title?: string;
}

interface TreemapProps {
  items: TreemapItem[];
  /** Aspect ratio of the drawing area (width / height). */
  aspect?: number;
  valueSuffix?: string;
  onSelect?: (item: TreemapItem) => void;
  selectedKey?: string | null;
}

interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
  item: TreemapItem;
}

const WIDTH = 100;

/**
 * Minimal squarified treemap: places items (sorted by value, descending) into
 * rows/columns of the remaining rectangle, keeping tiles close to square.
 */
function layout(items: TreemapItem[], width: number, height: number): Rect[] {
  const sorted = [...items].filter((item) => item.value > 0).sort((a, b) => b.value - a.value);
  const total = sorted.reduce((sum, item) => sum + item.value, 0);
  if (total === 0) {
    return [];
  }
  const scale = (width * height) / total;
  const rects: Rect[] = [];

  let x = 0;
  let y = 0;
  let remainingW = width;
  let remainingH = height;
  let index = 0;

  while (index < sorted.length) {
    const horizontal = remainingW >= remainingH; // lay the next strip along the shorter side
    const side = horizontal ? remainingH : remainingW;

    // Grow the strip while the worst tile aspect ratio keeps improving.
    let best: TreemapItem[] = [sorted[index]];
    let bestWorst = worstAspect(best, side, scale);
    let next = index + 1;
    while (next < sorted.length) {
      const candidate = [...best, sorted[next]];
      const candidateWorst = worstAspect(candidate, side, scale);
      if (candidateWorst <= bestWorst) {
        best = candidate;
        bestWorst = candidateWorst;
        next += 1;
      } else {
        break;
      }
    }

    const stripArea = best.reduce((sum, item) => sum + item.value, 0) * scale;
    const stripThickness = stripArea / side;
    let offset = 0;
    for (const item of best) {
      const tileLength = (item.value * scale) / stripThickness;
      rects.push(
        horizontal
          ? { x, y: y + offset, w: stripThickness, h: tileLength, item }
          : { x: x + offset, y, w: tileLength, h: stripThickness, item },
      );
      offset += tileLength;
    }

    if (horizontal) {
      x += stripThickness;
      remainingW -= stripThickness;
    } else {
      y += stripThickness;
      remainingH -= stripThickness;
    }
    index += best.length;
  }
  return rects;
}

function worstAspect(items: TreemapItem[], side: number, scale: number): number {
  const area = items.reduce((sum, item) => sum + item.value, 0) * scale;
  const thickness = area / side;
  let worst = 1;
  for (const item of items) {
    const length = (item.value * scale) / thickness;
    const ratio = Math.max(thickness / length, length / thickness);
    worst = Math.max(worst, ratio);
  }
  return worst;
}

const TILE_CLASSES = ["treemap-tile-a", "treemap-tile-b", "treemap-tile-c", "treemap-tile-d"];

export function Treemap({ items, aspect = 1.9, valueSuffix = "", onSelect, selectedKey }: TreemapProps) {
  const height = WIDTH / aspect;
  const rects = layout(items, WIDTH, height);

  return (
    <svg
      className="treemap"
      viewBox={`0 0 ${WIDTH} ${height}`}
      role="img"
      aria-label="Treemap"
      preserveAspectRatio="xMidYMid meet"
    >
      {rects.map((rect, index) => {
        // Every tile gets its full label, shrinking the font as far as needed;
        // clicking a tile is the reliable way to read the small ones.
        const fitByWidth = (rect.w - 2) / (rect.item.label.length * 0.52);
        const fitByHeight = rect.h / 2.4;
        const fontSize = Math.max(0.9, Math.min(3.2, fitByWidth, fitByHeight));
        const showValue = rect.h > fontSize * 2.6 + 4;
        const isSelected = selectedKey != null && rect.item.key === selectedKey;
        return (
          <g
            key={rect.item.key}
            className={`${TILE_CLASSES[index % TILE_CLASSES.length]}${isSelected ? " treemap-selected" : ""}${onSelect ? " treemap-clickable" : ""}`}
            onClick={onSelect ? () => onSelect(rect.item) : undefined}
          >
            <rect x={rect.x} y={rect.y} width={rect.w} height={rect.h} rx={0.7} className="treemap-rect">
              <title>{rect.item.title ?? `${rect.item.label}: ${rect.item.value}${valueSuffix}`}</title>
            </rect>
            <text
              x={rect.x + 1.2}
              y={rect.y + fontSize + 0.8}
              fontSize={fontSize}
              className="treemap-label"
            >
              {rect.item.label}
            </text>
            {showValue ? (
              <text
                x={rect.x + 1.2}
                y={rect.y + fontSize * 2.2 + 1.6}
                fontSize={fontSize * 0.9}
                className="treemap-value"
              >
                {rect.item.value}
                {valueSuffix}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}
