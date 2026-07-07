"use client";

import { useMemo, useState } from "react";
import { AssetTag, LagBadge, PartyTag, SideTag, TickerLink } from "@/components/tags";
import { band, shortDate } from "@/lib/format";

export type FeedRow = {
  id: string;
  src: "congress" | "insider";
  person: string;
  chamber: string;
  party: string;
  title: string;
  ticker: string;
  type: "stock" | "option" | "etf" | "other";
  side: "buy" | "sell";
  lo: number;
  hi: number;
  tx: string;
  filed: string;
  lag: number;
  opt: string | null;
  plan: boolean;
  url: string;
};

const PAGE = 250;

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`mono rounded-sm border px-2 py-1 text-[10px] uppercase tracking-[0.1em] transition-colors ${
        active
          ? "border-brass/70 bg-brass/10 text-brass"
          : "border-border text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

export function FeedTable({ rows }: { rows: FeedRow[] }) {
  const [source, setSource] = useState<"all" | "house" | "senate" | "insider">("all");
  const [party, setParty] = useState<"all" | "D" | "R">("all");
  const [side, setSide] = useState<"all" | "buy" | "sell">("all");
  const [optionsOnly, setOptionsOnly] = useState(false);
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(PAGE);

  const filtered = useMemo(() => {
    const needle = q.trim().toUpperCase();
    return rows.filter((r) => {
      if (source === "insider" && r.src !== "insider") return false;
      if ((source === "house" || source === "senate") && r.chamber !== source) return false;
      if (party !== "all") {
        const p = r.party[0]?.toUpperCase() ?? "";
        if (p !== party) return false;
        if (r.src !== "congress") return false;
      }
      if (side !== "all" && r.side !== side) return false;
      if (optionsOnly && r.type !== "option") return false;
      if (needle && !r.ticker.includes(needle) && !r.person.toUpperCase().includes(needle))
        return false;
      return true;
    });
  }, [rows, source, party, side, optionsOnly, q]);

  const shown = filtered.slice(0, limit);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex gap-1" role="group" aria-label="Filter by source">
          {(["all", "house", "senate", "insider"] as const).map((v) => (
            <FilterButton key={v} active={source === v} onClick={() => setSource(v)}>
              {v}
            </FilterButton>
          ))}
        </div>
        <div className="flex gap-1" role="group" aria-label="Filter by party">
          {(["all", "D", "R"] as const).map((v) => (
            <FilterButton key={v} active={party === v} onClick={() => setParty(v)}>
              {v === "all" ? "any party" : v}
            </FilterButton>
          ))}
        </div>
        <div className="flex gap-1" role="group" aria-label="Filter by side">
          {(["all", "buy", "sell"] as const).map((v) => (
            <FilterButton key={v} active={side === v} onClick={() => setSide(v)}>
              {v === "all" ? "both sides" : v}
            </FilterButton>
          ))}
        </div>
        <FilterButton active={optionsOnly} onClick={() => setOptionsOnly(!optionsOnly)}>
          ⚡ options only
        </FilterButton>
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setLimit(PAGE);
          }}
          placeholder="ticker or name…"
          aria-label="Search ticker or person"
          className="mono h-7 w-44 rounded-sm border border-border bg-secondary px-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-2 focus:outline-ring"
        />
        <span className="mono ml-auto text-[11px] tabular-nums text-muted-foreground">
          {filtered.length.toLocaleString()} rows
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full min-w-[880px] text-left text-[13px]">
          <thead>
            <tr className="mono border-b border-border text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
              <th className="px-3 py-2.5 font-medium">Filed</th>
              <th className="px-3 py-2.5 font-medium">Who</th>
              <th className="px-3 py-2.5 font-medium">Side</th>
              <th className="px-3 py-2.5 font-medium">Ticker</th>
              <th className="px-3 py-2.5 font-medium">Type</th>
              <th className="px-3 py-2.5 text-right font-medium">Amount</th>
              <th className="px-3 py-2.5 text-right font-medium">Lag</th>
              <th className="px-3 py-2.5 font-medium">Filing</th>
            </tr>
          </thead>
          <tbody className="ledger align-top">
            {shown.map((r) => (
              <tr key={r.id} className="hover:bg-accent/40">
                <td className="mono whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">
                  {shortDate(r.filed)}
                </td>
                <td className="px-3 py-2">
                  <div className="font-medium text-foreground">{r.person}</div>
                  <div className="text-[11px] text-muted-foreground">
                    {r.src === "congress" ? (
                      <PartyTag party={r.party} chamber={r.chamber} />
                    ) : (
                      <span className="mono text-[11px]">{r.title || "Insider"}</span>
                    )}
                  </div>
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  <SideTag side={r.side} planned={r.plan} />
                </td>
                <td className="px-3 py-2">
                  <TickerLink ticker={r.ticker} />
                  {r.opt ? (
                    <div className="mt-0.5 max-w-[260px] text-[11px] leading-snug text-brass/90">
                      {r.opt}
                    </div>
                  ) : null}
                </td>
                <td className="px-3 py-2">
                  <AssetTag type={r.type} />
                </td>
                <td className="mono whitespace-nowrap px-3 py-2 text-right tabular-nums">
                  {band(r.lo, r.hi)}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right">
                  <LagBadge days={r.lag} />
                </td>
                <td className="px-3 py-2">
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mono text-[11px] text-muted-foreground underline-offset-2 hover:text-brass hover:underline"
                  >
                    source ↗
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {shown.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            No filings match these filters — clear one and try again.
          </p>
        ) : null}
      </div>

      {filtered.length > shown.length ? (
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={() => setLimit(limit + PAGE)}
            className="mono rounded-sm border border-border px-4 py-2 text-[11px] uppercase tracking-[0.12em] text-muted-foreground hover:border-brass/60 hover:text-brass"
          >
            show {Math.min(PAGE, filtered.length - shown.length)} more
          </button>
        </div>
      ) : null}
    </div>
  );
}
