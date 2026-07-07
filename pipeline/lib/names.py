"""Match disclosure filer names to congress-legislators member records.

Disclosure sources spell names loosely ("Tommy Tuberville", "Rudy C. Yakym III",
"A. Mitchell Mcconnell, Jr."). Matching is chamber-scoped, keyed on last name,
then scored on first name / nickname / initial. Ambiguous names get no match
(empty committees) rather than a wrong one.
"""
from __future__ import annotations

import re
import unicodedata

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "md", "mr", "mrs", "ms", "hon", "dr"}

NICKNAMES = {
    "bill": "william", "billy": "william", "will": "william", "liam": "william",
    "bob": "robert", "rob": "robert", "bobby": "robert", "robby": "robert",
    "mike": "michael", "jim": "james", "jimmy": "james", "jamie": "james",
    "tom": "thomas", "tommy": "thomas", "dan": "daniel", "danny": "daniel",
    "dave": "david", "rick": "richard", "rich": "richard", "dick": "richard",
    "chris": "christopher", "topher": "christopher", "chuck": "charles",
    "charlie": "charles", "jeff": "jeffrey", "greg": "gregory", "ted": "edward",
    "ed": "edward", "eddie": "edward", "tim": "timothy", "joe": "joseph",
    "joey": "joseph", "tony": "anthony", "steve": "steven", "andy": "andrew",
    "drew": "andrew", "ron": "ronald", "ronny": "ronald", "don": "donald",
    "ben": "benjamin", "sam": "samuel", "pat": "patrick", "nick": "nicholas",
    "matt": "matthew", "ken": "kenneth", "kenny": "kenneth", "cindy": "cynthia",
    "debbie": "deborah", "deb": "deborah", "liz": "elizabeth", "beth": "elizabeth",
    "betty": "elizabeth", "katie": "katherine", "kate": "katherine",
    "kathy": "katherine", "maggie": "margaret", "peggy": "margaret",
    "jack": "john", "johnny": "john", "jon": "jonathan", "abe": "abraham",
    "alex": "alexander", "fred": "frederick", "gabe": "gabriel", "hal": "harold",
    "hank": "henry", "harry": "henry", "larry": "lawrence", "lou": "louis",
    "max": "maxwell", "ray": "raymond", "russ": "russell", "stan": "stanley",
    "terry": "terence", "vince": "vincent", "walt": "walter", "wes": "wesley",
    "zach": "zachary", "gus": "augustus", "cliff": "clifford", "clint": "clinton",
    "curt": "curtis", "norm": "norman", "phil": "philip", "ralph": "rudolph",
    "rudy": "rudolph", "art": "arthur", "bernie": "bernard", "brad": "bradley",
    "bret": "brett", "cal": "calvin", "cam": "cameron", "carl": "carlton",
    "mitch": "mitchell", "marty": "martin", "nate": "nathan", "nat": "nathaniel",
    "pete": "peter", "randy": "randall", "sandy": "alexander", "sid": "sidney",
    "sol": "solomon", "vic": "victor",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_tokens(name: str) -> list[str]:
    s = _strip_accents(str(name or "")).lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    return [t for t in s.split() if t and t not in SUFFIXES]


def _first_score(a: str, b: str) -> int:
    """Score similarity of two first-name tokens."""
    if not a or not b:
        return 0
    if a == b:
        return 4
    if NICKNAMES.get(a) == b or NICKNAMES.get(b) == a:
        return 3
    if len(a) >= 3 and (a.startswith(b) or b.startswith(a)):
        return 2
    if a[0] == b[0] and (len(a) == 1 or len(b) == 1):
        return 1
    return 0


class MemberIndex:
    """Index of members.json records for fuzzy filer-name lookup."""

    def __init__(self, members: list[dict]):
        self.by_last: dict[tuple[str, str], list[dict]] = {}
        for m in members:
            toks = norm_tokens(m.get("last", "")) or norm_tokens(m.get("name", ""))[-1:]
            if not toks:
                continue
            key = (m.get("chamber", ""), toks[-1])
            self.by_last.setdefault(key, []).append(m)

    def match(self, name: str, chamber: str) -> dict | None:
        toks = norm_tokens(name)
        if not toks:
            return None
        # try the last 1-2 tokens as the surname (handles "Van Hollen", "Scott Franklin")
        candidates: list[dict] = []
        for last in {toks[-1], " ".join(toks[-2:])} if len(toks) > 1 else {toks[-1]}:
            candidates.extend(self.by_last.get((chamber, last.split()[-1]), []))
        if not candidates:
            return None
        first = toks[0]
        scored = []
        for m in candidates:
            m_firsts = norm_tokens(m.get("first", "")) + norm_tokens(m.get("nickname", ""))
            # a filer may write a middle name first ("A. Mitchell McConnell")
            f_toks = [t for t in toks[:-1]] or [first]
            best = max((_first_score(a, b) for a in f_toks for b in m_firsts), default=0)
            scored.append((best, m))
        scored.sort(key=lambda x: -x[0])
        if not scored or scored[0][0] == 0:
            # unique last name in the chamber is convincing enough on its own
            uniq = {id(m) for _, m in scored}
            return scored[0][1] if len(uniq) == 1 and len(candidates) == 1 else None
        if len(scored) > 1 and scored[0][0] == scored[1][0] and scored[0][1] is not scored[1][1]:
            return None  # ambiguous
        return scored[0][1]
