"""
2026 FIFA World Cup knockout bracket structure and projection.

Format: 48 teams in 12 groups (A-L). Top 2 of each group + the 8 best
third-placed teams advance to a Round of 32, then single elimination
through to the final.

All match numbers and group-position pairings below are the official FIFA
structure. The "third-place slots" each have a fixed set of 5 eligible
groups; once the 8 qualifying third-place groups are known, each is assigned
to a slot via the eligibility constraint (FIFA Annex C). We resolve that
assignment with constraint matching rather than hardcoding the 495-row table.
"""

GROUPS = list("ABCDEFGHIJKL")

# --- Round of 32: (match_no, home_slot, away_slot) -------------------------
# Slot codes: "1X"=winner group X, "2X"=runner-up group X, "3?<set>"=best
# third-place team drawn from one of the listed groups.
ROUND_OF_32 = [
    (73, "2A", "2B"),
    (74, "1E", "3?ABCDF"),
    (75, "1F", "2C"),
    (76, "1C", "2F"),
    (77, "1I", "3?CDFGH"),
    (78, "2E", "2I"),
    (79, "1A", "3?CEFHI"),
    (80, "1L", "3?EHIJK"),
    (81, "1D", "3?BEFIJ"),
    (82, "1G", "3?AEHIJ"),
    (83, "2K", "2L"),
    (84, "1H", "2J"),
    (85, "1B", "3?EFGIJ"),
    (86, "1J", "2H"),
    (87, "1K", "3?DEIJL"),
    (88, "2D", "2G"),
]

# Third-place slots, in the order they must be filled, with eligible groups.
THIRD_PLACE_SLOTS = [
    (74, set("ABCDF")),
    (77, set("CDFGH")),
    (79, set("CEFHI")),
    (80, set("EHIJK")),
    (81, set("BEFIJ")),
    (82, set("AEHIJ")),
    (85, set("EFGIJ")),
    (87, set("DEIJL")),
]

# --- Later rounds: (match_no, winner_of_a, winner_of_b) --------------------
ROUND_OF_16 = [
    (89, 73, 75), (90, 74, 77), (91, 76, 78), (92, 79, 80),
    (93, 83, 84), (94, 81, 82), (95, 86, 88), (96, 85, 87),
]
QUARTER_FINALS = [
    (97, 89, 90), (98, 93, 94), (99, 91, 92), (100, 95, 96),
]
SEMI_FINALS = [(101, 97, 98), (102, 99, 100)]
FINAL = (104, 101, 102)


def assign_third_places(qualifying_groups):
    """Map the 8 qualifying third-place groups to their R32 slot match numbers.

    Returns {match_no: group_letter}, or None if no valid assignment exists
    (which only happens with bad input, never with a real set of 8 groups).
    """
    groups = list(qualifying_groups)
    if len(groups) != 8:
        raise ValueError(f"need exactly 8 third-place groups, got {len(groups)}")

    slots = THIRD_PLACE_SLOTS

    def backtrack(i, used, acc):
        if i == len(slots):
            return acc
        match_no, eligible = slots[i]
        # Most-constrained-first ordering happens naturally; try eligible groups.
        for g in groups:
            if g in used or g not in eligible:
                continue
            acc[match_no] = g
            res = backtrack(i + 1, used | {g}, acc)
            if res is not None:
                return res
            del acc[match_no]
        return None

    return backtrack(0, set(), {})
