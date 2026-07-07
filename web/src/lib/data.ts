import fs from "node:fs";
import path from "node:path";

/* ---------- types mirroring /data JSON ---------- */

export type Role = { chamber: string; party: string; committees: string[] };

export type Trade = {
  id: string;
  source: "congress" | "insider";
  person: string;
  role: Role;
  insider_title: string;
  ticker: string;
  asset_type: "stock" | "option" | "etf" | "other";
  side: "buy" | "sell";
  amount_low: number;
  amount_high: number;
  tx_date: string;
  filed_date: string;
  lag_days: number;
  option_detail: string | null;
  planned_10b5_1: boolean;
  source_url: string;
};

export type SignalDetail = {
  fired: boolean;
  points: number;
  [k: string]: unknown;
};

export type Candidate = {
  ticker: string;
  name: string | null;
  sectors: string[];
  score: number;
  signals: Record<string, SignalDetail>;
  evidence: { id: string; signal: string }[];
  stats: Record<string, number>;
};

export type BriefPick = {
  ticker: string;
  direction: "long" | "avoid";
  conviction: "high" | "medium" | "speculative";
  thesis: string;
  evidence_ids: string[];
  key_risks: string[];
  invalidation: string;
  expression: { simple: string; defined_risk_note?: string | null };
};

export type Brief = {
  status: "ok" | "engine_only";
  model?: string;
  generated_at?: string;
  date?: string;
  as_of?: string;
  regime_note?: string;
  picks?: BriefPick[];
  caution_list?: { ticker: string; reason: string; evidence_ids?: string[] }[];
  skipped?: { ticker: string; reason: string }[];
};

export type Member = {
  bioguide: string;
  former?: boolean;
  name: string;
  first: string;
  last: string;
  chamber: "house" | "senate";
  party: string;
  state: string;
  committees: { id: string; name: string }[];
  sectors: string[];
};

export type LeaderRow = {
  person: string;
  party: string;
  chamber: string;
  state: string;
  trades_scored: number;
  avg_excess: number;
  win_rate: number;
  best: { ticker: string; side: string; excess: number };
  worst: { ticker: string; side: string; excess: number };
};

/* ---------- loading ---------- */

function dataDir(): string {
  for (const p of [
    path.resolve(process.cwd(), "..", "data"),
    path.resolve(process.cwd(), "data"),
  ]) {
    if (fs.existsSync(path.join(p, "trades.json"))) return p;
  }
  throw new Error("data directory not found");
}

const cache = new Map<string, unknown>();

function read<T>(name: string): T {
  if (!cache.has(name)) {
    cache.set(name, JSON.parse(fs.readFileSync(path.join(dataDir(), name), "utf-8")));
  }
  return cache.get(name) as T;
}

export function getTrades(): { generated_at: string | null; trades: Trade[] } {
  return read("trades.json");
}

export function getCandidates(): {
  generated_at: string | null;
  as_of: string | null;
  candidates: Candidate[];
  caution: Candidate[];
} {
  return read("candidates.json");
}

export function getBrief(): Brief {
  return read("brief-latest.json");
}

export function getMembers(): Member[] {
  return read<{ members: Member[] }>("members.json").members;
}

export function getPrices(): Record<string, [string, number][]> {
  return read<{ series: Record<string, [string, number][]> }>("prices.json").series;
}

export function getLeaderboard(): { min_trades: number; members: LeaderRow[] } {
  return read("leaderboard.json");
}

export function getTickersMeta(): Record<
  string,
  { name: string | null; sectors: string[]; sic_desc: string | null }
> {
  return read<{ tickers: Record<string, { name: string | null; sectors: string[]; sic_desc: string | null }> }>(
    "tickers.json",
  ).tickers;
}

export function getCommitteeMap(): Record<string, { name: string; sectors: string[] }> {
  return read("committee_sector_map.json");
}

export function getStatus(): {
  sources: Record<string, { ok: boolean; detail: string; count: number | null; at: string }>;
} {
  return read("status.json");
}

/* ---------- derived views (build-time only) ---------- */

export function tradesById(): Map<string, Trade> {
  return new Map(getTrades().trades.map((t) => [t.id, t]));
}

export type Cluster = {
  ticker: string;
  name: string | null;
  side: "buy" | "sell";
  members: string[];
  trades: Trade[];
  start: string;
  end: string;
};

/** All >=3-distinct-member same-side groups within a 30-day sliding window. */
export function activeClusters(windowDays = 30, minMembers = 3): Cluster[] {
  const meta = getTickersMeta();
  const byKey = new Map<string, Trade[]>();
  for (const t of getTrades().trades) {
    if (t.source !== "congress" || !t.tx_date) continue;
    const key = `${t.ticker}|${t.side}`;
    (byKey.get(key) ?? byKey.set(key, []).get(key)!).push(t);
  }
  const out: Cluster[] = [];
  for (const [key, list] of byKey) {
    const [ticker, side] = key.split("|") as [string, "buy" | "sell"];
    const sorted = [...list].sort((a, b) => a.tx_date.localeCompare(b.tx_date));
    let best: Trade[] = [];
    for (let i = 0; i < sorted.length; i++) {
      const end = addDays(sorted[i].tx_date, windowDays);
      const span = sorted.filter((t, j) => j >= i && t.tx_date <= end);
      if (distinct(span) > distinct(best)) best = span;
    }
    if (distinct(best) >= minMembers) {
      out.push({
        ticker,
        name: meta[ticker]?.name ?? null,
        side,
        members: [...new Set(best.map((t) => t.person))].sort(),
        trades: best,
        start: best[0].tx_date,
        end: best[best.length - 1].tx_date,
      });
    }
  }
  return out.sort((a, b) => b.end.localeCompare(a.end) || a.ticker.localeCompare(b.ticker));
}

export type Convergence = {
  ticker: string;
  name: string | null;
  congressBuys: Trade[];
  insiderBuys: Trade[];
};

/** Tickers where congress bought AND >=2 distinct non-10b5-1 insiders bought within 45 days. */
export function convergenceEvents(windowDays = 45): Convergence[] {
  const meta = getTickersMeta();
  const byTicker = new Map<string, Trade[]>();
  for (const t of getTrades().trades) {
    (byTicker.get(t.ticker) ?? byTicker.set(t.ticker, []).get(t.ticker)!).push(t);
  }
  const out: Convergence[] = [];
  for (const [ticker, list] of byTicker) {
    const cBuys = list.filter((t) => t.source === "congress" && t.side === "buy");
    const iBuys = list.filter(
      (t) => t.source === "insider" && t.side === "buy" && !t.planned_10b5_1,
    );
    const near = iBuys.filter((ib) =>
      cBuys.some((cb) => Math.abs(daysBetween(ib.tx_date, cb.tx_date)) <= windowDays),
    );
    if (cBuys.length && new Set(near.map((t) => t.person)).size >= 2) {
      out.push({ ticker, name: meta[ticker]?.name ?? null, congressBuys: cBuys, insiderBuys: near });
    }
  }
  return out.sort(
    (a, b) =>
      latest(b.insiderBuys).localeCompare(latest(a.insiderBuys)) ||
      a.ticker.localeCompare(b.ticker),
  );
}

const distinct = (ts: Trade[]) => new Set(ts.map((t) => t.person)).size;
const latest = (ts: Trade[]) =>
  ts.reduce((m, t) => (t.tx_date > m ? t.tx_date : m), "0000-00-00");

function addDays(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function daysBetween(a: string, b: string): number {
  return Math.round(
    (new Date(a + "T00:00:00Z").getTime() - new Date(b + "T00:00:00Z").getTime()) / 86_400_000,
  );
}
