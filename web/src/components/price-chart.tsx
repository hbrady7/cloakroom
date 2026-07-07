import type { Trade } from "@/lib/data";

/**
 * Static SVG price line with disclosure markers.
 * Buy = ▲ green, sell = ▼ red (shape + color, never color alone);
 * congress = filled, insider = hollow. Each marker carries a <title>
 * tooltip; the full trade table always sits next to the chart.
 */
export function PriceChart({
  series,
  trades,
  height = 180,
  showAxis = true,
}: {
  series: [string, number][];
  trades: Trade[];
  height?: number;
  showAxis?: boolean;
}) {
  if (!series || series.length < 2) {
    return (
      <p className="rounded-md border border-border bg-card px-4 py-8 text-center text-xs text-muted-foreground">
        No price history available for this ticker.
      </p>
    );
  }
  const W = 720;
  const H = height;
  const PAD = { t: 14, r: 54, b: showAxis ? 18 : 6, l: 8 };
  const dates = series.map((r) => r[0]);
  const closes = series.map((r) => r[1]);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;

  const x = (i: number) =>
    PAD.l + (i / (series.length - 1)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - min) / span) * (H - PAD.t - PAD.b);

  const dateIndex = new Map(dates.map((d, i) => [d, i]));
  const nearestIndex = (iso: string): number | null => {
    if (dateIndex.has(iso)) return dateIndex.get(iso)!;
    if (iso < dates[0] || iso > dates[dates.length - 1]) return null;
    for (let i = 0; i < dates.length; i++) if (dates[i] >= iso) return i;
    return null;
  };

  const path = closes
    .map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join("");

  const markers = trades
    .map((t) => ({ t, i: nearestIndex(t.tx_date) }))
    .filter((m): m is { t: Trade; i: number } => m.i !== null);

  const last = closes[closes.length - 1];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      role="img"
      aria-label={`Price history with ${markers.length} disclosed trades marked`}
    >
      {/* recessive gridline at min/max */}
      {[min, max].map((v) => (
        <line
          key={v}
          x1={PAD.l}
          x2={W - PAD.r}
          y1={y(v)}
          y2={y(v)}
          stroke="var(--border)"
          strokeDasharray="2 4"
          strokeWidth="1"
        />
      ))}
      <path d={path} fill="none" stroke="var(--muted-foreground)" strokeWidth="2" />

      {markers.map(({ t, i }, k) => {
        const cx = x(i);
        const cy = y(closes[i]);
        const buy = t.side === "buy";
        const color = buy ? "var(--buy)" : "var(--sell)";
        const size = 5.5;
        const points = buy
          ? `${cx},${cy - size} ${cx - size},${cy + size} ${cx + size},${cy + size}`
          : `${cx},${cy + size} ${cx - size},${cy - size} ${cx + size},${cy - size}`;
        const congress = t.source === "congress";
        return (
          <polygon
            key={`${t.id}-${k}`}
            points={points}
            fill={congress ? color : "var(--card)"}
            stroke={congress ? "var(--card)" : color}
            strokeWidth="2"
          >
            <title>
              {`${t.person} — ${t.side.toUpperCase()} ${t.ticker} ${t.tx_date}${t.asset_type === "option" ? " (option)" : ""}`}
            </title>
          </polygon>
        );
      })}

      {/* direct label on the last price */}
      <circle cx={x(closes.length - 1)} cy={y(last)} r="3" fill="var(--brass)" />
      <text
        x={x(closes.length - 1) + 8}
        y={y(last) + 3.5}
        fill="var(--brass)"
        fontSize="11"
        fontFamily="var(--font-plex-mono)"
      >
        {last >= 100 ? last.toFixed(0) : last.toFixed(2)}
      </text>

      {showAxis ? (
        <>
          <text x={PAD.l} y={H - 4} fill="var(--muted-foreground)" fontSize="10" fontFamily="var(--font-plex-mono)">
            {dates[0]}
          </text>
          <text
            x={W - PAD.r}
            y={H - 4}
            textAnchor="end"
            fill="var(--muted-foreground)"
            fontSize="10"
            fontFamily="var(--font-plex-mono)"
          >
            {dates[dates.length - 1]}
          </text>
        </>
      ) : null}
    </svg>
  );
}
