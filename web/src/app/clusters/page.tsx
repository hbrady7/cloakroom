import {
  activeClusters,
  convergenceEvents,
  type Cluster,
  type Convergence,
} from "@/lib/data";
import { band, money, shortDate } from "@/lib/format";
import { Plate, SectionHeader, SideTag, TickerLink } from "@/components/tags";

export const metadata = { title: "Clusters — CLOAKROOM" };

export default function ClustersPage() {
  const clusters = activeClusters();
  const buys = clusters.filter((c) => c.side === "buy");
  const sells = clusters.filter((c) => c.side === "sell");
  const conv = convergenceEvents();

  return (
    <div className="space-y-10">
      <SectionHeader
        plate="form cr-3 · coordinated activity"
        title="Clusters & Convergence"
        right={
          <p className="mono text-[11px] text-muted-foreground">
            ≥3 members · 30-day window · convergence pairs congress with Form 4 buys
          </p>
        }
      />

      <section>
        <Plate>convergence events · congress + open-market insiders, 45 days</Plate>
        {conv.length === 0 ? (
          <Empty note="No convergence events in the current window." />
        ) : (
          <div className="mt-3 grid gap-4 lg:grid-cols-2">
            {conv.map((c) => (
              <ConvergenceCard key={c.ticker} event={c} />
            ))}
          </div>
        )}
      </section>

      <section>
        <Plate>buy clusters</Plate>
        {buys.length === 0 ? (
          <Empty note="No active buy clusters." />
        ) : (
          <div className="mt-3 space-y-3">
            {buys.map((c) => (
              <ClusterRow key={`${c.ticker}-buy`} cluster={c} />
            ))}
          </div>
        )}
      </section>

      <section>
        <Plate>sell clusters</Plate>
        {sells.length === 0 ? (
          <Empty note="No active sell clusters." />
        ) : (
          <div className="mt-3 space-y-3">
            {sells.map((c) => (
              <ClusterRow key={`${c.ticker}-sell`} cluster={c} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Empty({ note }: { note: string }) {
  return (
    <p className="mt-3 rounded-md border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
      {note}
    </p>
  );
}

/** Horizontal mini-timeline: each trade as a tick positioned by tx_date. */
function Timeline({
  trades,
  start,
  end,
  lane,
}: {
  trades: { tx_date: string; side: string; person: string; id: string }[];
  start: string;
  end: string;
  lane?: "congress" | "insider";
}) {
  const t0 = new Date(start + "T00:00:00Z").getTime() - 86_400_000 * 2;
  const t1 = new Date(end + "T00:00:00Z").getTime() + 86_400_000 * 2;
  const span = Math.max(t1 - t0, 1);
  const W = 320;
  const H = 22;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-[22px] w-full max-w-[320px]" aria-hidden>
      <line x1="0" x2={W} y1={H / 2} y2={H / 2} stroke="var(--border)" strokeWidth="1" />
      {trades.map((t, i) => {
        const x = ((new Date(t.tx_date + "T00:00:00Z").getTime() - t0) / span) * W;
        const buy = t.side === "buy";
        const color = buy ? "var(--buy)" : "var(--sell)";
        const s = 4.5;
        const cy = H / 2;
        const pts = buy
          ? `${x},${cy - s} ${x - s},${cy + s} ${x + s},${cy + s}`
          : `${x},${cy + s} ${x - s},${cy - s} ${x + s},${cy - s}`;
        return (
          <polygon
            key={`${t.id}-${i}`}
            points={pts}
            fill={lane === "insider" ? "var(--card)" : color}
            stroke={lane === "insider" ? color : "var(--card)"}
            strokeWidth="1.5"
          >
            <title>{`${t.person} · ${t.tx_date}`}</title>
          </polygon>
        );
      })}
    </svg>
  );
}

function ClusterRow({ cluster }: { cluster: Cluster }) {
  const mid = cluster.trades.reduce((s, t) => s + (t.amount_low + t.amount_high) / 2, 0);
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-border bg-card px-4 py-3">
      <div className="w-24 shrink-0">
        <TickerLink ticker={cluster.ticker} className="text-lg" />
        <div className="mt-0.5">
          <SideTag side={cluster.side} />
        </div>
      </div>
      <div className="min-w-[200px] flex-1">
        <Timeline trades={cluster.trades} start={cluster.start} end={cluster.end} />
        <p className="mono mt-1 text-[10px] text-muted-foreground">
          {shortDate(cluster.start)} → {shortDate(cluster.end)}
        </p>
      </div>
      <div className="mono text-right text-[11px] leading-relaxed text-muted-foreground">
        <p>
          <span className="text-foreground">{cluster.members.length}</span> members ·{" "}
          <span className="text-foreground">{cluster.trades.length}</span> trades · ~
          {money(mid)} midpoint
        </p>
        <p className="max-w-[380px] truncate" title={cluster.members.join(", ")}>
          {cluster.members.join(" · ")}
        </p>
      </div>
    </div>
  );
}

function ConvergenceCard({ event }: { event: Convergence }) {
  const all = [...event.congressBuys, ...event.insiderBuys].map((t) => t.tx_date).sort();
  const start = all[0];
  const end = all[all.length - 1];
  const insiderNames = [...new Set(event.insiderBuys.map((t) => t.person))];
  const memberNames = [...new Set(event.congressBuys.map((t) => t.person))];
  return (
    <div className="rounded-lg border border-buy/40 bg-card p-4">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <TickerLink ticker={event.ticker} className="text-xl" />
          <span className="ml-2 text-xs text-muted-foreground">{event.name}</span>
        </div>
        <span className="mono text-[10px] uppercase tracking-[0.12em] text-buy">
          convergence
        </span>
      </div>
      <div className="mt-3 space-y-2">
        <div className="flex items-center gap-3">
          <span className="mono w-20 shrink-0 text-[10px] uppercase text-muted-foreground">
            congress
          </span>
          <Timeline trades={event.congressBuys} start={start} end={end} lane="congress" />
        </div>
        <div className="flex items-center gap-3">
          <span className="mono w-20 shrink-0 text-[10px] uppercase text-muted-foreground">
            insiders
          </span>
          <Timeline trades={event.insiderBuys} start={start} end={end} lane="insider" />
        </div>
      </div>
      <div className="mt-3 space-y-1 border-t border-border pt-3 text-[11px] leading-relaxed text-muted-foreground">
        <p>
          <span className="text-foreground">{memberNames.length}</span> member
          {memberNames.length === 1 ? "" : "s"}: {memberNames.join(", ")}
        </p>
        <p>
          <span className="text-foreground">{insiderNames.length}</span> insider
          {insiderNames.length === 1 ? "" : "s"} (open-market, non-10b5-1):{" "}
          {insiderNames.slice(0, 6).join(", ")}
          {insiderNames.length > 6 ? ` +${insiderNames.length - 6} more` : ""}
        </p>
        <p>
          largest congressional lot:{" "}
          {band(
            Math.max(...event.congressBuys.map((t) => t.amount_low)),
            Math.max(...event.congressBuys.map((t) => t.amount_high)),
          )}
        </p>
      </div>
    </div>
  );
}
