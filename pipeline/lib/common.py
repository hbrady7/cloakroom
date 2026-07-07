"""Shared plumbing for all pipeline scripts.

Pure helpers (bands, dates, ids, trade building) are offline and unit-tested.
HTTP helpers add retries + polite per-session rate limiting.
Every fetcher is fail-soft: on error it keeps the last-good committed JSON.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# SEC fair-access format: "<tool> <contact email>" (parenthesized variants 403)
USER_AGENT = "cloakroom-research hollisbrady2004@gmail.com"

WINDOW_DAYS = int(os.environ.get("CLOAKROOM_WINDOW_DAYS", "180"))

TRADE_KEYS = [
    "id", "source", "person", "role", "insider_title", "ticker", "asset_type",
    "side", "amount_low", "amount_high", "tx_date", "filed_date", "lag_days",
    "option_detail", "planned_10b5_1", "source_url",
]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> date:
    return datetime.now(timezone.utc).date()


def window_start(days: int = WINDOW_DAYS) -> date:
    return today() - timedelta(days=days)


# ---------------------------------------------------------------- HTTP

def http_session(rps: float = 2.0) -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3, connect=3, read=2, backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "HEAD"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers["User-Agent"] = USER_AGENT
    s._min_interval = 1.0 / rps  # type: ignore[attr-defined]
    s._last_req = 0.0  # type: ignore[attr-defined]
    return s


def _throttle(s: requests.Session) -> None:
    wait = getattr(s, "_min_interval", 0) - (time.monotonic() - getattr(s, "_last_req", 0))
    if wait > 0:
        time.sleep(wait)


def polite_get(s: requests.Session, url: str, **kw) -> requests.Response:
    _throttle(s)
    kw.setdefault("timeout", (10, 90))
    r = s.get(url, **kw)
    s._last_req = time.monotonic()  # type: ignore[attr-defined]
    return r


def polite_post(s: requests.Session, url: str, **kw) -> requests.Response:
    _throttle(s)
    kw.setdefault("timeout", (10, 90))
    r = s.post(url, **kw)
    s._last_req = time.monotonic()  # type: ignore[attr-defined]
    return r


# ---------------------------------------------------------------- JSON io

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, p)


# ---------------------------------------------------------------- status / fail-soft

def set_status(source: str, ok: bool, detail: str = "", count=None) -> None:
    p = DATA / "status.json"
    st = load_json(p, {"sources": {}}) or {"sources": {}}
    st.setdefault("sources", {})[source] = {
        "ok": bool(ok), "detail": str(detail)[:500], "count": count, "at": utcnow_iso(),
    }
    save_json(p, st)


def run_fail_soft(source: str, main_fn) -> None:
    """Run a fetcher main(); on any exception log it, record status, exit 0.

    The last-good committed JSON in /data stays untouched, so downstream
    steps and the site keep working.
    """
    try:
        main_fn()
    except Exception as e:  # noqa: BLE001 - deliberately broad: fail-soft boundary
        traceback.print_exc()
        set_status(source, False, f"{type(e).__name__}: {e}")
        print(f"[{source}] FAILED - keeping last-good data", file=sys.stderr)
    sys.exit(0)


# ---------------------------------------------------------------- parsing helpers

_BAND_RE = re.compile(r"\$([\d,]+)\s*-+\s*\$?([\d,]+)")
_OVER_RE = re.compile(r"(?:over|>)\s*\$([\d,]+)", re.I)
_PLUS_RE = re.compile(r"\$([\d,]+)\s*\+")


def parse_band(text) -> tuple[int, int]:
    """Disclosure amount band -> (low, high) dollars.

    '$15,001 - $50,000' -> (15001, 50000); 'Over $50,000,000' -> (50000001, 100000000).
    Unknown/unparseable -> (0, 0).
    """
    t = " ".join(str(text or "").split())
    m = _BAND_RE.search(t)
    if m:
        lo = int(m.group(1).replace(",", ""))
        hi = int(m.group(2).replace(",", ""))
        return (lo, hi) if lo <= hi else (hi, lo)
    m = _OVER_RE.search(t)
    if m:
        lo = int(m.group(1).replace(",", ""))
        return lo + 1, lo * 2
    m = _PLUS_RE.search(t)
    if m:
        lo = int(m.group(1).replace(",", ""))
        return lo, lo * 2
    return 0, 0


def parse_date(s) -> date | None:
    s = str(s or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def iso(d: date | None) -> str | None:
    return d.strftime("%Y-%m-%d") if d else None


TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]{0,5}([.\-][A-Z0-9]{1,3})?$")


def clean_ticker(t) -> str | None:
    t = str(t or "").strip().upper().rstrip(".")
    if t in ("", "--", "N/A", "NA", "NONE", "-"):
        return None
    return t if TICKER_RE.match(t) else None


def trade_id(source: str, *parts) -> str:
    prefix = "C" if source == "congress" else "I"
    h = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{h}"


def make_trade(*, id, source, person, role=None, insider_title="", ticker,
               asset_type="stock", side, amount_low=0, amount_high=0,
               tx_date, filed_date, option_detail=None, planned_10b5_1=False,
               source_url="") -> dict:
    """Build one trade in the unified schema. tx_date/filed_date are datetime.date."""
    lag = 0
    if tx_date and filed_date:
        lag = max(0, (filed_date - tx_date).days)
    return {
        "id": id,
        "source": source,
        "person": person,
        "role": role or {"chamber": "", "party": "", "committees": []},
        "insider_title": insider_title,
        "ticker": ticker,
        "asset_type": asset_type,
        "side": side,
        "amount_low": int(amount_low),
        "amount_high": int(amount_high),
        "tx_date": iso(tx_date),
        "filed_date": iso(filed_date),
        "lag_days": lag,
        "option_detail": option_detail,
        "planned_10b5_1": bool(planned_10b5_1),
        "source_url": source_url,
    }
