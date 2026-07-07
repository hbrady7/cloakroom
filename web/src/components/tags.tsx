import Link from "next/link";
import type { Trade } from "@/lib/data";
import { partyAbbr, shortDate } from "@/lib/format";

export function SideTag({ side, planned }: { side: "buy" | "sell"; planned?: boolean }) {
  const buy = side === "buy";
  return (
    <span
      className={`mono inline-flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide ${buy ? "text-buy" : "text-sell"}`}
    >
      <span aria-hidden>{buy ? "▲" : "▼"}</span>
      {side}
      {planned ? <span className="text-muted-foreground normal-case">·10b5-1</span> : null}
    </span>
  );
}

export function PartyTag({ party, state, chamber }: { party: string; state?: string; chamber?: string }) {
  const p = partyAbbr(party);
  const color = p === "D" ? "text-dem" : p === "R" ? "text-gop" : "text-ind";
  const ch = chamber === "senate" ? "Sen" : chamber === "house" ? "Rep" : "";
  return (
    <span className={`mono text-[11px] ${color}`}>
      {ch ? `${ch} · ` : ""}
      {p}
      {state ? `–${state}` : ""}
    </span>
  );
}

export function AssetTag({ type }: { type: Trade["asset_type"] }) {
  const style =
    type === "option"
      ? "border-brass/60 text-brass"
      : "border-border text-muted-foreground";
  return (
    <span
      className={`mono inline-block rounded-sm border px-1 py-px text-[10px] uppercase tracking-wider ${style}`}
    >
      {type}
    </span>
  );
}

export function ConvictionBadge({ level }: { level: "high" | "medium" | "speculative" }) {
  const styles = {
    high: "border-buy/60 text-buy",
    medium: "border-brass/60 text-brass",
    speculative: "border-border text-muted-foreground",
  } as const;
  return (
    <span
      className={`mono inline-block rounded-sm border px-1.5 py-0.5 text-[10px] uppercase tracking-[0.12em] ${styles[level]}`}
    >
      {level}
    </span>
  );
}

export function LagBadge({ days }: { days: number }) {
  const cls =
    days <= 7 ? "text-buy" : days <= 30 ? "text-muted-foreground" : "text-caution";
  return (
    <span className={`mono text-[11px] tabular-nums ${cls}`} title="Days between trade and disclosure">
      {days}d lag
    </span>
  );
}

/**
 * The signature device: every claim carries a chip naming the underlying
 * filing record; the chip links straight to the government document.
 */
export function EvidenceChip({ trade, id }: { trade?: Trade; id: string }) {
  const short = id.slice(0, 8);
  if (!trade) {
    return <span className="mono text-[10px] text-muted-foreground">{short}</span>;
  }
  return (
    <a
      href={trade.source_url || "#"}
      target="_blank"
      rel="noopener noreferrer"
      title={`${trade.person} — ${trade.side} ${trade.ticker} — filed ${shortDate(trade.filed_date)}`}
      className="mono inline-block rounded-sm border border-border bg-secondary px-1.5 py-0.5 text-[10px] tracking-wide text-muted-foreground transition-colors hover:border-brass/60 hover:text-brass"
    >
      {short}
    </a>
  );
}

export function TickerLink({ ticker, className = "" }: { ticker: string; className?: string }) {
  return (
    <Link
      href={`/t/${ticker}`}
      className={`mono font-semibold text-foreground hover:text-brass ${className}`}
    >
      {ticker}
    </Link>
  );
}

export function Plate({ children }: { children: React.ReactNode }) {
  return <p className="form-plate">{children}</p>;
}

export function SectionHeader({
  plate,
  title,
  right,
}: {
  plate: string;
  title: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-5 flex items-end justify-between gap-4 border-b border-border pb-3">
      <div>
        <Plate>{plate}</Plate>
        <h1 className="display mt-1 text-2xl font-bold tracking-tight text-foreground">
          {title}
        </h1>
      </div>
      {right ? <div className="text-right">{right}</div> : null}
    </div>
  );
}
