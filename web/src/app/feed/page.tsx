import { getTrades } from "@/lib/data";
import { SectionHeader } from "@/components/tags";
import { FeedTable, type FeedRow } from "./feed-table";

export const metadata = { title: "Trade feed — CLOAKROOM" };

export default function FeedPage() {
  const { trades } = getTrades();
  const rows: FeedRow[] = trades.map((t) => ({
    id: t.id,
    src: t.source,
    person: t.person,
    chamber: t.role.chamber,
    party: t.role.party,
    title: t.insider_title,
    ticker: t.ticker,
    type: t.asset_type,
    side: t.side,
    lo: t.amount_low,
    hi: t.amount_high,
    tx: t.tx_date,
    filed: t.filed_date,
    lag: t.lag_days,
    opt: t.option_detail,
    plan: t.planned_10b5_1,
    url: t.source_url,
  }));

  return (
    <div>
      <SectionHeader
        plate="form cr-2 · transaction tape"
        title="Feed"
        right={
          <p className="mono text-[11px] text-muted-foreground">
            {rows.length.toLocaleString()} filings · rolling 180 days
          </p>
        }
      />
      <FeedTable rows={rows} />
    </div>
  );
}
