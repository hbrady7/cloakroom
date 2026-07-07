from lib.names import MemberIndex, norm_tokens

MEMBERS = [
    {"name": "Mitch McConnell", "first": "Mitch", "last": "McConnell",
     "nickname": "", "chamber": "senate", "party": "Republican",
     "committees": [{"id": "SSAP", "name": "Senate Appropriations"}]},
    {"name": "Thomas Tuberville", "first": "Thomas", "last": "Tuberville",
     "nickname": "Tommy", "chamber": "senate", "party": "Republican", "committees": []},
    {"name": "Rudy Yakym", "first": "Rudy", "last": "Yakym",
     "nickname": "", "chamber": "house", "party": "Republican", "committees": []},
    {"name": "Daniel Webster", "first": "Daniel", "last": "Webster",
     "nickname": "", "chamber": "house", "party": "Republican", "committees": []},
    {"name": "Scott Peters", "first": "Scott", "last": "Peters",
     "nickname": "", "chamber": "house", "party": "Democrat", "committees": []},
    {"name": "Gary Peters", "first": "Gary", "last": "Peters",
     "nickname": "", "chamber": "senate", "party": "Democrat", "committees": []},
]


def idx():
    return MemberIndex(MEMBERS)


def test_norm_tokens_strips_suffixes_and_punct():
    assert norm_tokens("Hon. Rudy C. Yakym III") == ["rudy", "c", "yakym"]


def test_exact_match():
    assert idx().match("Daniel Webster", "house")["name"] == "Daniel Webster"


def test_nickname_match():
    assert idx().match("Tommy Tuberville", "senate")["name"] == "Thomas Tuberville"


def test_middle_initial_and_suffix_noise():
    assert idx().match("Rudy C. Yakym III", "house")["name"] == "Rudy Yakym"


def test_chamber_scoping_disambiguates_same_last_name():
    assert idx().match("Scott Peters", "house")["name"] == "Scott Peters"
    assert idx().match("Gary Peters", "senate")["name"] == "Gary Peters"


def test_unknown_name_returns_none():
    assert idx().match("Zebulon Quimby", "house") is None
