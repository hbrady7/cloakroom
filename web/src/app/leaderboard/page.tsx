import { getLeaderboard } from "@/lib/data";
import { pct } from "@/lib/format";
import { PartyTag, SectionHeader, TickerLink } from "@/components/tags";

export const metadata = { title: "Leaderboard — CLOAKROOM" };

export default function LeaderboardPage() {
  const { members, min_trades } = getLeaderboard();

  return (
    <div>
      <SectionHeader
        plate="form cr-5 · member performance"
        title="Leaderboard"
        right={
          <p className="mono max-w-[320px] text-right text-[11px] leading-relaxed text-muted-foreground">
            Excess return vs SPY from the first close after each disclosure to
            the latest close. Minimum {min_trades} scored trades.
          </p>
        }
      />

      {members.length === 0 ? (
        <p className="rounded-md border border-border bg-card px-4 py-8 text-sm text-muted-foreground">
          Not enough scored trades yet — the leaderboard fills as price history
          accumulates.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[760px] text-left text-[13px]">
            <thead>
              <tr className="mono border-b border-border text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                <th className="px-3 py-2.5 font-medium">#</th>
                <th className="px-3 py-2.5 font-medium">Member</th>
                <th className="px-3 py-2.5 text-right font-medium">Scored trades</th>
                <th className="px-3 py-2.5 text-right font-medium">Avg excess vs SPY</th>
                <th className="px-3 py-2.5 text-right font-medium">Win rate</th>
                <th className="px-3 py-2.5 font-medium">Best call</th>
                <th className="px-3 py-2.5 font-medium">Worst call</th>
              </tr>
            </thead>
            <tbody className="ledger">
              {members.map((m, i) => (
                <tr key={m.person} className="hover:bg-accent/40">
                  <td className="mono px-3 py-2 tabular-nums text-muted-foreground">
                    {i + 1}
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium text-foreground">{m.person}</div>
                    <PartyTag party={m.party} state={m.state} chamber={m.chamber} />
                  </td>
                  <td className="mono px-3 py-2 text-right tabular-nums">
                    {m.trades_scored}
                  </td>
                  <td
                    className={`mono px-3 py-2 text-right font-semibold tabular-nums ${m.avg_excess >= 0 ? "text-buy" : "text-sell"}`}
                  >
                    {pct(m.avg_excess)}
                  </td>
                  <td className="mono px-3 py-2 text-right tabular-nums text-muted-foreground">
                    {(m.win_rate * 100).toFixed(0)}%
                  </td>
                  <td className="px-3 py-2">
                    <CallCell ticker={m.best.ticker} side={m.best.side} excess={m.best.excess} />
                  </td>
                  <td className="px-3 py-2">
                    <CallCell ticker={m.worst.ticker} side={m.worst.side} excess={m.worst.excess} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-4 max-w-3xl text-xs leading-relaxed text-muted-foreground">
        Method: a buy is credited with the ticker&apos;s return minus SPY over the same
        span; a sell is credited with SPY minus the ticker (credit for exiting what
        then underperformed). Entries use the first close on or after the public
        disclosure date — the first day anyone reading the filing could act — not
        the member&apos;s own (earlier) trade date. Bands, partial fills, and options
        legs are not weighted.
      </p>
    </div>
  );
}

function CallCell({ ticker, side, excess }: { ticker: string; side: string; excess: number }) {
  return (
    <span className="mono text-[12px]">
      <TickerLink ticker={ticker} className="text-[12px]" />{" "}
      <span className="text-muted-foreground">{side}</span>{" "}
      <span className={excess >= 0 ? "text-buy" : "text-sell"}>{pct(excess)}</span>
    </span>
  );
}
