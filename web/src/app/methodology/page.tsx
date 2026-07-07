import { getCommitteeMap } from "@/lib/data";
import { Plate, SectionHeader } from "@/components/tags";

export const metadata = { title: "Methodology — CLOAKROOM" };

const SIGNALS = [
  {
    name: "Convergence",
    weight: "0–35",
    detail:
      "Congressional buys AND ≥2 distinct open-market insider buyers (Form 4 code P, not marked 10b5-1) on the same ticker within 45 days. The strongest pattern the engine knows: two unrelated informed groups arriving at the same name.",
  },
  {
    name: "Cluster buys",
    weight: "0–30",
    detail:
      "≥3 distinct members buying the same ticker inside any sliding 30-day window, scaled up to 6+ members. Same-member repeat buys don't count.",
  },
  {
    name: "Committee alignment",
    weight: "0–20",
    detail:
      "A buyer sits on a committee overseeing the ticker's sector. Sectors come from the issuer's SEC SIC code; committee jurisdictions from the static map below.",
  },
  {
    name: "Options conviction",
    weight: "0–15",
    detail:
      "Any disclosed congressional option position (asset class [OP] in the PTR, with its Description terms captured). Leverage is conviction; large option lots (≥$250k band midpoint) score the full boost.",
  },
  {
    name: "Size",
    weight: "0–10",
    detail:
      "Log-scale on the disclosure band midpoint (congress) or exact dollar value (insiders): $1k → 1, $100k → 3, $10M → 5.",
  },
];

const SOURCES = [
  {
    name: "House Clerk financial disclosures",
    url: "https://disclosures-clerk.house.gov",
    detail:
      "Annual FD index ZIP → PTR PDFs parsed with pdfplumber. Paper (scanned) filings carry no text layer and are recorded but unparsed.",
  },
  {
    name: "Senate eFD",
    url: "https://efdsearch.senate.gov",
    detail:
      "Official electronic financial disclosure search, scraped politely (the Senate Stock Watcher aggregate this project was designed around died in 2021; its path remains the coded primary with eFD as live fallback).",
  },
  {
    name: "SEC EDGAR",
    url: "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany",
    detail:
      "Submissions API + Form 4 XML for every ticker with congressional activity: insider name, title, transaction codes P/S, shares, price, and the Rule 10b5-1(c) checkbox.",
  },
  {
    name: "unitedstates/congress-legislators",
    url: "https://github.com/unitedstates/congress-legislators",
    detail: "Member metadata: party, state, chamber, committee assignments (plus recent departures).",
  },
  {
    name: "stooq.com / Yahoo Finance",
    url: "https://stooq.com",
    detail: "Free end-of-day closes, 120 trading days per ticker plus SPY, with automatic failover.",
  },
];

export default function MethodologyPage() {
  const committeeMap = Object.entries(getCommitteeMap()).filter(
    ([, v]) => v.sectors.length > 0,
  );

  return (
    <div className="max-w-4xl space-y-10">
      <SectionHeader plate="form cr-6 · how this works" title="Methodology" />

      <section className="space-y-3 text-sm leading-relaxed text-foreground/90">
        <p>
          CLOAKROOM ingests two public paper trails — congressional STOCK Act
          periodic transaction reports and SEC Form 4 insider filings — and asks
          one question: <em>where do the incentives of people with privileged
          vantage points visibly converge?</em>
        </p>
        <p>
          A deterministic engine scores every ticker with congressional activity
          in the rolling 180-day window. No model, no randomness: the same
          inputs always produce the same output, and every point on the board
          traces to specific filings you can open. A daily Claude pass then
          writes the narrative brief — under hard rules that it may only use
          the engine&apos;s dossier, must cite evidence IDs for every claim, and is
          schema-validated with the citations cross-checked against the actual
          trade records. If validation fails twice, the site falls back to raw
          engine output rather than publish an ungrounded brief.
        </p>
      </section>

      <section>
        <Plate>signal weights</Plate>
        <div className="mt-3 overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[560px] text-left text-[13px]">
            <thead>
              <tr className="mono border-b border-border text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                <th className="px-4 py-2.5 font-medium">Signal</th>
                <th className="px-4 py-2.5 font-medium">Points</th>
                <th className="px-4 py-2.5 font-medium">Definition</th>
              </tr>
            </thead>
            <tbody className="ledger align-top">
              {SIGNALS.map((s) => (
                <tr key={s.name}>
                  <td className="whitespace-nowrap px-4 py-2.5 font-medium text-foreground">
                    {s.name}
                  </td>
                  <td className="mono whitespace-nowrap px-4 py-2.5 text-brass">{s.weight}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{s.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
          Every component is multiplied by exponential staleness decay on
          information age (as-of date minus trade date) with a 14-day half-life
          — a 44-day-old disclosure carries ~11% of a fresh one — then summed
          and capped at 100. The caution list mirrors the negative side: sell
          clusters and officer distribution (≥2 officers selling, 10b5-1 plans
          half-weighted), plus a committee-aligned-seller bonus. Broad index
          ETFs (SPY, QQQ, VOO…) are excluded from long candidates; sector funds
          stay eligible. Congressional amounts are band midpoints — bands are
          all the law requires.
        </p>
      </section>

      <section>
        <Plate>data sources · all free, all official or community-maintained</Plate>
        <ul className="mt-3 space-y-3">
          {SOURCES.map((s) => (
            <li key={s.name} className="rounded-lg border border-border bg-card px-4 py-3">
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-foreground underline-offset-2 hover:text-brass hover:underline"
              >
                {s.name} ↗
              </a>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{s.detail}</p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <Plate>committee → sector map (hand-authored, versioned in the repo)</Plate>
        <div className="mt-3 overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[480px] text-left text-[13px]">
            <thead>
              <tr className="mono border-b border-border text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                <th className="px-4 py-2.5 font-medium">Committee</th>
                <th className="px-4 py-2.5 font-medium">Oversees</th>
              </tr>
            </thead>
            <tbody className="ledger">
              {committeeMap.map(([id, c]) => (
                <tr key={id}>
                  <td className="px-4 py-2 text-foreground">
                    {c.name} <span className="mono text-[10px] text-muted-foreground">{id}</span>
                  </td>
                  <td className="mono px-4 py-2 text-xs text-brass">
                    {c.sectors.join(" · ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <Plate>honest limits</Plate>
        <ul className="mt-3 list-inside space-y-2 text-sm leading-relaxed text-muted-foreground">
          <li>
            · Disclosures lag reality by up to 45 days (and occasionally far
            more); the lag badge on every row shows exactly how stale each
            filing was.
          </li>
          <li>
            · Paper/scanned filings (a minority of House PTRs, a few Senate
            ones) have no text layer and are logged but unparsed.
          </li>
          <li>
            · Amount bands mean position size is a range, not a number.
            Spouse/dependent trades are attributed to the member, as the STOCK
            Act does.
          </li>
          <li>
            · Members trade for many reasons — index rebalancing, managed
            accounts, divorce. Clusters and convergence reduce but do not
            eliminate innocent explanations.
          </li>
        </ul>
      </section>

      <section className="rounded-lg border border-caution/40 bg-caution/5 p-5 text-sm leading-relaxed">
        <p className="form-plate">disclaimer</p>
        <p className="mt-2 text-foreground/90">
          This is informational research derived from public STOCK Act and SEC
          EDGAR filings. It is not investment advice, not a recommendation, and
          not an offer to buy or sell any security. Filings lag; data can be
          wrong or incomplete; past performance of any filer implies nothing
          about the future. This site holds no positions, executes nothing, and
          charges nothing.
        </p>
      </section>
    </div>
  );
}
