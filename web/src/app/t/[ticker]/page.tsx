import { notFound } from "next/navigation";
import {
  getCandidates,
  getPrices,
  getTickersMeta,
  getTrades,
  tradesById,
  type Candidate,
} from "@/lib/data";
import { band, shortDate } from "@/lib/format";
import { PriceChart } from "@/components/price-chart";
import {
  AssetTag,
  EvidenceChip,
  LagBadge,
  PartyTag,
  Plate,
  SectionHeader,
  SideTag,
} from "@/components/tags";

export const dynamicParams = false;

export function generateStaticParams() {
  const tickers = new Set(getTrades().trades.map((t) => t.ticker));
  return [...tickers].map((ticker) => ({ ticker }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  return { title: `${ticker} — CLOAKROOM` };
}

export default async function TickerPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  const trades = getTrades().trades.filter((t) => t.ticker === ticker);
  if (!trades.length) notFound();

  const meta = getTickersMeta()[ticker];
  const series = getPrices()[ticker] ?? [];
  const engine = getCandidates();
  const candidate = engine.candidates.find((c) => c.ticker === ticker);
  const caution = engine.caution.find((c) => c.ticker === ticker);
  const byId = tradesById();

  const congress = trades.filter((t) => t.source === "congress");
  const insiders = trades.filter((t) => t.source === "insider");

  return (
    <div className="space-y-8">
      <SectionHeader
        plate={`form cr-4 · single name${meta?.sic_desc ? ` · sic: ${meta.sic_desc.toLowerCase()}` : ""}`}
        title={ticker}
        right={
          <div className="mono text-right text-[11px] text-muted-foreground">
            <p>{meta?.name ?? "—"}</p>
            <p className="mt-0.5 text-brass">{(meta?.sectors ?? []).join(" · ") || "unsectored"}</p>
          </div>
        }
      />

      <section className="rounded-lg border border-border bg-card p-4">
        <div className="mb-2 flex items-center justify-between">
          <Plate>120-day price · disclosed trades marked</Plate>
          <p className="mono text-[10px] text-muted-foreground">
            ▲ buy · ▼ sell · filled = congress · hollow = insider
          </p>
        </div>
        <PriceChart series={series} trades={trades} />
      </section>

      {(candidate || caution) && (
        <section className="grid gap-4 lg:grid-cols-2">
          {candidate ? <SignalPanel entry={candidate} tone="long" byId={byId} /> : null}
          {caution ? <SignalPanel entry={caution} tone="caution" byId={byId} /> : null}
        </section>
      )}

      <section className="grid gap-6 xl:grid-cols-2">
        <TradeTable title={`congressional activity · ${congress.length}`} trades={congress} kind="congress" />
        <TradeTable title={`insider activity (form 4) · ${insiders.length}`} trades={insiders} kind="insider" />
      </section>
    </div>
  );
}

function SignalPanel({
  entry,
  tone,
  byId,
}: {
  entry: Candidate;
  tone: "long" | "caution";
  byId: ReturnType<typeof tradesById>;
}) {
  const border = tone === "long" ? "border-buy/40" : "border-caution/40";
  const label = tone === "long" ? "engine long candidate" : "engine caution flag";
  const color = tone === "long" ? "text-buy" : "text-caution";
  return (
    <div className={`rounded-lg border ${border} bg-card p-4`}>
      <div className="flex items-baseline justify-between">
        <Plate>{label}</Plate>
        <span className={`mono text-sm font-semibold ${color}`}>
          {entry.score.toFixed(1)}
        </span>
      </div>
      <ul className="mt-3 space-y-1.5 text-xs">
        {Object.entries(entry.signals).map(([name, s]) => (
          <li key={name} className="flex items-center justify-between gap-3">
            <span className={`mono uppercase tracking-wide ${s.fired ? "text-foreground" : "text-muted-foreground/60"}`}>
              {s.fired ? "●" : "○"} {name.replace(/_/g, " ")}
            </span>
            <span className="mono tabular-nums text-muted-foreground">
              {s.points > 0 ? `+${s.points.toFixed(1)}` : "—"}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border pt-3">
        {entry.evidence.slice(0, 14).map((e) => (
          <EvidenceChip key={`${e.id}-${e.signal}`} id={e.id} trade={byId.get(e.id)} />
        ))}
      </div>
    </div>
  );
}

function TradeTable({
  title,
  trades,
  kind,
}: {
  title: string;
  trades: ReturnType<typeof getTrades>["trades"];
  kind: "congress" | "insider";
}) {
  return (
    <div>
      <Plate>{title}</Plate>
      {trades.length === 0 ? (
        <p className="mt-2 rounded-md border border-border bg-card px-4 py-6 text-xs text-muted-foreground">
          None disclosed in the rolling window.
        </p>
      ) : (
        <div className="mt-2 overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[520px] text-left text-[13px]">
            <thead>
              <tr className="mono border-b border-border text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                <th className="px-3 py-2 font-medium">Who</th>
                <th className="px-3 py-2 font-medium">Side</th>
                <th className="px-3 py-2 text-right font-medium">Amount</th>
                <th className="px-3 py-2 font-medium">Traded</th>
                <th className="px-3 py-2 text-right font-medium">Lag</th>
              </tr>
            </thead>
            <tbody className="ledger align-top">
              {trades.map((t) => (
                <tr key={t.id} className="hover:bg-accent/40">
                  <td className="px-3 py-2">
                    <a
                      href={t.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-foreground underline-offset-2 hover:text-brass hover:underline"
                    >
                      {t.person}
                    </a>
                    <div className="text-[11px] text-muted-foreground">
                      {kind === "congress" ? (
                        <PartyTag party={t.role.party} chamber={t.role.chamber} />
                      ) : (
                        <span className="mono">{t.insider_title || "Insider"}</span>
                      )}
                    </div>
                    {t.option_detail ? (
                      <div className="mt-0.5 max-w-[280px] text-[11px] leading-snug text-brass/90">
                        {t.option_detail}
                      </div>
                    ) : null}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <SideTag side={t.side} planned={t.planned_10b5_1} />
                    {t.asset_type !== "stock" ? (
                      <div className="mt-1">
                        <AssetTag type={t.asset_type} />
                      </div>
                    ) : null}
                  </td>
                  <td className="mono whitespace-nowrap px-3 py-2 text-right tabular-nums">
                    {band(t.amount_low, t.amount_high)}
                  </td>
                  <td className="mono whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">
                    {shortDate(t.tx_date)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right">
                    <LagBadge days={t.lag_days} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
