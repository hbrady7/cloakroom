# CLOAKROOM

**Free politician + insider trade intelligence.** Congressional STOCK Act
disclosures and SEC Form 4 insider filings, scored by a deterministic signal
engine, briefed daily by Claude, published as a static site. Total marginal
cost: **$0**.

> Research only. Disclosures lag reality by up to 45 days. Nothing here is
> investment advice, and nothing here touches money — this repo briefs.

## Architecture

```
GitHub Actions (cron, weekdays ~6:30am CT)
│
├─ pipeline/fetch_members.py   congress-legislators YAML ─┐
├─ pipeline/fetch_senate.py    Senate eFD (official) ─────┤
├─ pipeline/fetch_house.py     House Clerk PTR PDFs ──────┼─► /data/*.json
├─ pipeline/fetch_edgar.py     SEC EDGAR Form 4 XML ──────┤   (committed —
├─ pipeline/merge_trades.py    unified 180-day trades ────┤    the "database")
├─ pipeline/fetch_prices.py    stooq → yfinance EOD ──────┘
├─ pipeline/score.py           deterministic signal engine ─► candidates.json
├─ pipeline/leaderboard.py     member returns vs SPY ───────► leaderboard.json
├─ pipeline/run_brief.py       claude -p (subscription OAuth) ► brief-latest.json
│                              schema + citation validation, engine_only fallback
└─ git commit /data && push ──► Vercel auto-deploys /web (Next.js 15, fully static)
```

Every trade carries a deterministic evidence ID (`C-…` congressional,
`I-…` insider). The engine's candidates reference those IDs; the Claude brief
may only cite those IDs; the validator rejects any brief that cites an ID or
ticker that doesn't exist in the data. The site renders the chips as deep
links to the actual filings.

## The $0 cost table

| Piece | Provider | Why it's free |
|---|---|---|
| Hosting | Vercel Hobby | static Next.js site, no functions needed |
| Compute | GitHub Actions | public repos get unlimited standard-runner minutes |
| Senate trades | efdsearch.senate.gov | official public disclosure system |
| House trades | disclosures-clerk.house.gov | official Clerk index + PTR PDFs |
| Insider trades | SEC EDGAR (data.sec.gov) | official, free, fair-access rules honored |
| Prices | stooq.com → yfinance | free EOD closes, 120 trading days |
| Member metadata | unitedstates/congress-legislators | community-maintained public YAML |
| AI brief | Claude via `claude -p` | covered by an existing Claude subscription (OAuth token), no API key |
| Push alerts (optional) | ntfy.sh | free public pub-sub topics |
| Database | none | committed JSON in `/data` is the database |

## Repo layout

- `/web` — Next.js 15 + Tailwind v4 + shadcn/ui dashboard. Statically
  generated from `/data` at build time; no runtime backend.
- `/pipeline` — Python 3.12 fetchers, signal engine, briefing layer. Runs in
  GitHub Actions (or locally). Every fetcher is fail-soft: on error the
  last-good committed JSON stays in place and the site never breaks.
- `/data` — committed JSON outputs (rolling 180-day window).

## Signals (see `/methodology` on the site)

| Signal | Weight | Definition |
|---|---|---|
| Convergence | 0–35 | congress buys + ≥2 distinct open-market (non-10b5-1) insider buyers within 45d |
| Cluster buys | 0–30 | ≥3 distinct members, same ticker, sliding 30-day window |
| Committee alignment | 0–20 | buyer's committee oversees the ticker's sector (SIC ↔ static committee map) |
| Options conviction | 0–15 | any disclosed congressional option position (terms parsed from the PTR) |
| Size | 0–10 | log scale on band midpoint / dollar value |

All components decay exponentially on information age (14-day half-life),
then sum, capped at 100. Caution list: sell clusters + officer distribution
(10b5-1 sales half-weighted). Deterministic: same inputs → identical output.

## Setup (one-time, ~10 minutes)

1. **Fork/clone**, push to your GitHub as a **public** repo (public =
   unlimited free Actions minutes).
2. **Claude brief token**: run `claude setup-token` locally (needs a Claude
   subscription), copy the OAuth token, save it as the repo secret
   `CLAUDE_CODE_OAUTH_TOKEN`. Without it the workflow skips the brief and the
   site renders raw engine candidates — everything else still works.
3. **Vercel**: *Add New → Project → Import* the repo, set **Root Directory**
   to `web` (keep "Include source files outside of the Root Directory"
   enabled — the site reads `../data` at build time). `web/vercel.json`
   already pins `framework: nextjs`. Every push (including the bot's daily
   data commit) redeploys.
4. **Optional secrets**:
   - `NTFY_TOPIC` — a topic name on [ntfy.sh](https://ntfy.sh); the workflow
     posts the top-3 picks there each run (subscribe on your phone).
   - `FMP_KEY` — Financial Modeling Prep free-tier key; used only as an
     emergency fallback path and skipped silently when absent.
5. **First run**: Actions → *daily* → *Run workflow*, or wait for the cron
   (`30 11 * * 1-5`, ~6:30am CT weekdays).

### Local development

```sh
cd pipeline
uv venv --python 3.12 .venv && source .venv/bin/activate
pip install -r requirements.txt
python fetch_members.py && python fetch_senate.py && python fetch_house.py
python fetch_edgar.py && python merge_trades.py && python fetch_prices.py
python score.py && python leaderboard.py
pytest                      # 66+ tests, incl. exact-value real-filing fixtures

cd ../web
npm install && npm run build && npm run start
```

## Secrets referenced by the workflow

| Secret | Required | Purpose |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | no (brief skipped without it) | subscription-auth for `claude -p` |
| `NTFY_TOPIC` | no | free push notification with the top picks |
| `FMP_KEY` | no | optional FMP free-tier fallback; never required |

No paid APIs, no metered keys, no database, no execution code. The pipeline
identifies itself to SEC EDGAR with a proper User-Agent and stays well under
the fair-access rate limits; the eFD and Clerk fetchers are throttled and
incremental (seen-caches in `/data`).

## Disclaimer

Informational research derived from public STOCK Act and SEC EDGAR filings.
Disclosures lag reality by up to 45 days; congressional amounts are bands,
not exact sizes; filings can be amended or wrong. **Nothing here is
investment advice.** This project holds no positions and executes nothing.

MIT licensed.
