"""
Deterministic bracket projection from current standings.

Given group standings (which may be partial), resolve as many R32 slots as
possible into concrete teams. Slots that can't yet be resolved are "TBD".
"""

import bracket as B
from standings import rank_third_places


def _group_complete(table):
    return all(r["played"] >= 3 for r in table) and len(table) >= 4


def resolve_slots(standings):
    """Return {slot_code: team_or_None} for 1X / 2X slots, plus the
    third-place assignment {match_no: team_or_None}."""
    slots = {}
    for g, table in standings.items():
        slots[f"1{g}"] = table[0]["team"] if len(table) >= 1 else None
        slots[f"2{g}"] = table[1]["team"] if len(table) >= 2 else None

    third_assignment = {}
    groups_done = all(_group_complete(t) for t in standings.values()) \
        and len(standings) == 12
    if groups_done:
        thirds = rank_third_places(standings)
        qualifiers = thirds[:8]
        qual_groups = [t["group"] for t in qualifiers]
        by_group = {t["group"]: t["team"] for t in qualifiers}
        mapping = B.assign_third_places(qual_groups)  # {match_no: group}
        for match_no, grp in mapping.items():
            third_assignment[match_no] = by_group[grp]
    return slots, third_assignment


def project_round_of_32(standings):
    """Return list of {match, home, away} for the R32 (teams or 'TBD')."""
    slots, thirds = resolve_slots(standings)
    out = []
    for match_no, hs, as_ in B.ROUND_OF_32:
        home = slots.get(hs)
        if as_.startswith("3?"):
            away = thirds.get(match_no)
        else:
            away = slots.get(as_)
        out.append({
            "match": match_no,
            "home": home or "TBD",
            "away": away or "TBD",
            "home_slot": hs,
            "away_slot": as_,
        })
    return out
