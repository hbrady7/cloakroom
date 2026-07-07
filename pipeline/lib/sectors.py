"""Sector tagging: SIC code -> sector tags, matched against committee sectors.

The committee side of the mapping lives in data/committee_sector_map.json
(static, hand-authored, rendered on /methodology). Both sides share one
controlled vocabulary so `committee_sectors & ticker_sectors` is meaningful.
"""
from __future__ import annotations

from .common import DATA, load_json

SECTOR_VOCAB = [
    "ag", "aerospace", "banks", "biotech", "commodities", "cyber", "defense",
    "energy", "fintech", "food", "healthcare", "industrial", "insurance",
    "media", "mining", "pharma", "real_estate", "retail", "semis", "tech",
    "telecom", "transport", "utilities",
]

_RANGES: list[tuple[int, int, list[str]]] = [
    (100, 999, ["ag"]),
    (1000, 1299, ["mining", "commodities"]),
    (1300, 1399, ["energy"]),                    # oil & gas extraction
    (1400, 1499, ["mining", "commodities"]),
    (1500, 1799, ["industrial", "real_estate"]),  # construction
    (2000, 2199, ["food", "ag"]),
    (2800, 2829, ["industrial"]),                 # industrial chemicals
    (2833, 2836, ["pharma", "biotech"]),
    (2870, 2879, ["ag"]),                         # agricultural chemicals
    (2900, 2999, ["energy"]),                     # petroleum refining
    (3400, 3499, ["industrial", "defense"]),      # incl. 3480s ordnance
    (3500, 3569, ["industrial"]),
    (3570, 3579, ["tech"]),                       # computers
    (3600, 3669, ["industrial"]),
    (3670, 3679, ["semis", "tech"]),
    (3690, 3699, ["industrial"]),
    (3700, 3719, ["transport", "industrial"]),    # motor vehicles
    (3720, 3729, ["aerospace", "defense"]),
    (3730, 3759, ["transport", "industrial"]),
    (3760, 3769, ["aerospace", "defense"]),       # guided missiles, space
    (3810, 3812, ["defense", "aerospace"]),       # search & navigation systems
    (3820, 3829, ["healthcare", "tech"]),         # lab & measurement instruments
    (3840, 3851, ["healthcare"]),                 # medical devices
    (4000, 4799, ["transport"]),
    (4800, 4829, ["telecom"]),
    (4830, 4841, ["media", "telecom"]),
    (4880, 4899, ["telecom"]),
    (4900, 4939, ["utilities", "energy"]),
    (4940, 4999, ["utilities"]),
    (5000, 5999, ["retail"]),
    (6000, 6199, ["banks"]),
    (6200, 6299, ["fintech", "banks"]),           # brokers, exchanges
    (6300, 6499, ["insurance"]),
    (6500, 6599, ["real_estate"]),
    (6770, 6770, []),                             # blank checks / SPACs
    (6700, 6799, ["real_estate", "banks"]),       # incl. 6798 REITs
    (7000, 7299, ["retail"]),
    (7300, 7369, ["tech"]),                       # business services
    (7370, 7379, ["tech"]),                       # software & data processing
    (7380, 7389, ["tech"]),
    (7800, 7899, ["media"]),
    (8000, 8099, ["healthcare"]),
    (8700, 8730, ["industrial"]),
    (8731, 8731, ["biotech", "pharma"]),          # commercial physical/bio research
]


def sic_to_sectors(sic) -> list[str]:
    try:
        c = int(str(sic).strip() or 0)
    except (TypeError, ValueError):
        return []
    out: list[str] = []
    for lo, hi, tags in _RANGES:
        if lo <= c <= hi:
            for t in tags:
                if t not in out:
                    out.append(t)
            break  # ranges are ordered specific-enough; first hit wins
    return out


def committee_sector_map() -> dict:
    return load_json(DATA / "committee_sector_map.json", {}) or {}


def committee_sectors(thomas_ids: list[str]) -> list[str]:
    cmap = committee_sector_map()
    out: list[str] = []
    for cid in thomas_ids or []:
        for t in (cmap.get(cid, {}) or {}).get("sectors", []):
            if t not in out:
                out.append(t)
    return out
