# pipeline

Python 3.12. Runs only inside GitHub Actions (or locally for development).
Every script is fail-soft: on any fetch/parse failure it leaves the last-good
committed JSON in `/data` untouched and exits 0 so the rest of the run continues.

```
fetch_members.py   # E: congress-legislators YAML -> data/members.json
fetch_senate.py    # A: Senate Stock Watcher aggregate -> senate trades
fetch_house.py     # B: House Clerk PTR index + PDFs -> house trades
fetch_edgar.py     # C: SEC EDGAR Form 4 XML -> insider trades (+ ticker SIC sectors)
merge_trades.py    # A+B+C -> data/trades.json (unified schema, rolling 180d)
fetch_prices.py    # D: stooq EOD (yfinance fallback) -> data/prices.json
score.py           # deterministic signal engine -> data/candidates.json
leaderboard.py     # per-member returns vs SPY -> data/leaderboard.json
build_brief_input.py / validate_brief.py / run_brief.py  # Claude briefing layer
```

Local dev:

```sh
uv venv --python 3.12 .venv && source .venv/bin/activate
pip install -r requirements.txt
python fetch_members.py && python fetch_senate.py && python fetch_house.py
python fetch_edgar.py && python merge_trades.py && python fetch_prices.py
python score.py && python leaderboard.py
pytest
```
