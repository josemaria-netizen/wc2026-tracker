"""
Group standings computation with FIFA tiebreaker rules.

Input: a list of matches. Each match is a dict:
    {"group": "A", "home": "Mexico", "away": "South Korea",
     "home_goals": 2, "away_goals": 1}   # goals None/absent => not yet played

Output: per-group ordered standings, plus the cross-group ranking of
third-placed teams used to pick the 8 best.

FIFA group tiebreakers (in order):
  1. Points
  2. Goal difference
  3. Goals scored
  4. Head-to-head among tied teams (points, then GD, then goals)
  5. (fair play / drawing of lots — not modelled; we fall back to name)
"""

from collections import defaultdict


def _blank_row(team):
    return {"team": team, "played": 0, "won": 0, "drawn": 0, "lost": 0,
            "gf": 0, "ga": 0, "gd": 0, "points": 0}


def _is_played(m):
    # Live (in-play) games don't count toward the official table until final.
    return (m.get("home_goals") is not None
            and m.get("away_goals") is not None
            and not m.get("live"))


def compute_group(matches, teams=None):
    """Return ordered list of standing rows for one group's matches."""
    rows = {}
    if teams:
        for t in teams:
            rows[t] = _blank_row(t)

    for m in matches:
        for t in (m["home"], m["away"]):
            rows.setdefault(t, _blank_row(t))
        if not _is_played(m):
            continue
        hg, ag = m["home_goals"], m["away_goals"]
        h, a = rows[m["home"]], rows[m["away"]]
        h["played"] += 1; a["played"] += 1
        h["gf"] += hg; h["ga"] += ag
        a["gf"] += ag; a["ga"] += hg
        if hg > ag:
            h["won"] += 1; a["lost"] += 1; h["points"] += 3
        elif hg < ag:
            a["won"] += 1; h["lost"] += 1; a["points"] += 3
        else:
            h["drawn"] += 1; a["drawn"] += 1; h["points"] += 1; a["points"] += 1

    for r in rows.values():
        r["gd"] = r["gf"] - r["ga"]

    return _order(list(rows.values()), matches)


def _h2h_points(teams_set, matches):
    """Head-to-head mini-table among a set of tied teams."""
    sub = defaultdict(lambda: {"points": 0, "gd": 0, "gf": 0})
    for m in matches:
        if not _is_played(m):
            continue
        if m["home"] in teams_set and m["away"] in teams_set:
            hg, ag = m["home_goals"], m["away_goals"]
            sub[m["home"]]["gf"] += hg; sub[m["home"]]["gd"] += hg - ag
            sub[m["away"]]["gf"] += ag; sub[m["away"]]["gd"] += ag - hg
            if hg > ag:
                sub[m["home"]]["points"] += 3
            elif hg < ag:
                sub[m["away"]]["points"] += 3
            else:
                sub[m["home"]]["points"] += 1; sub[m["away"]]["points"] += 1
    return sub


def _order(rows, matches):
    def overall_key(r):
        return (r["points"], r["gd"], r["gf"])

    rows.sort(key=lambda r: (overall_key(r), r["team"]), reverse=False)
    rows.sort(key=overall_key, reverse=True)

    # Resolve ties with head-to-head among the tied cluster.
    ordered = []
    i = 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and overall_key(rows[j + 1]) == overall_key(rows[i]):
            j += 1
        cluster = rows[i:j + 1]
        if len(cluster) > 1:
            names = {r["team"] for r in cluster}
            h2h = _h2h_points(names, matches)
            cluster.sort(key=lambda r: r["team"])  # stable fallback
            cluster.sort(
                key=lambda r: (h2h[r["team"]]["points"], h2h[r["team"]]["gd"],
                               h2h[r["team"]]["gf"]),
                reverse=True,
            )
        ordered.extend(cluster)
        i = j + 1

    for rank, r in enumerate(ordered, 1):
        r["rank"] = rank
    return ordered


def all_groups(matches_by_group, teams_by_group=None):
    """Return {group: ordered standings} for every group present."""
    teams_by_group = teams_by_group or {}
    out = {}
    for g, ms in matches_by_group.items():
        out[g] = compute_group(ms, teams_by_group.get(g))
    return out


def rank_third_places(standings):
    """Rank all 3rd-placed teams across groups; return ordered list of dicts
    each carrying its group letter. Best 8 qualify."""
    thirds = []
    for g, table in standings.items():
        if len(table) >= 3:
            row = dict(table[2])
            row["group"] = g
            thirds.append(row)
    thirds.sort(key=lambda r: r["team"])
    thirds.sort(key=lambda r: (r["points"], r["gd"], r["gf"]), reverse=True)
    for rank, r in enumerate(thirds, 1):
        r["third_rank"] = rank
    return thirds
