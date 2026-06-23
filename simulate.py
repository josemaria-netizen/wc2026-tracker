"""
Monte-Carlo simulation of the rest of the tournament for advancement and
title odds.

Model
-----
Each team has a strength rating (Elo-like, default 1500). For a match we
derive an expected goal difference from the rating gap and draw each side's
goals from a Poisson distribution. Knockout draws go to penalties, decided by
a rating-weighted coin flip.

Ratings can be supplied externally (e.g. seeded FIFA/Elo ratings). If absent,
a team's rating is inferred from its group-stage results so far, blended with
a neutral prior, so the model self-calibrates as real results come in.
"""

import math
import random
from collections import defaultdict

import bracket as B
from standings import all_groups, rank_third_places

BASE_GOALS = 1.35          # league-average goals per team per match
RATING_TO_GOALS = 1 / 280  # how strongly a rating gap moves expected goals
PRIOR_RATING = 1500.0


def infer_ratings(standings, seed_ratings=None):
    """Blend any seeded ratings with form derived from results so far."""
    ratings = {}
    for table in standings.values():
        for r in table:
            form = 0.0
            if r["played"] > 0:
                ppg = r["points"] / r["played"]
                gd_pg = r["gd"] / r["played"]
                form = (ppg - 1.0) * 90 + gd_pg * 55
            base = (seed_ratings or {}).get(r["team"], PRIOR_RATING)
            # Weight observed form more as more matches are played.
            w = min(r["played"], 3) / 3 * 0.6
            ratings[r["team"]] = base * (1 - w) + (PRIOR_RATING + form) * w \
                if not seed_ratings or r["team"] not in seed_ratings \
                else base + form * w
    return ratings


def _sim_match(a, b, ratings, knockout=False, rng=random):
    ra = ratings.get(a, PRIOR_RATING)
    rb = ratings.get(b, PRIOR_RATING)
    diff = (ra - rb) * RATING_TO_GOALS
    la = max(0.15, BASE_GOALS + diff / 2)
    lb = max(0.15, BASE_GOALS - diff / 2)
    ga = _poisson(la, rng)
    gb = _poisson(lb, rng)
    if knockout and ga == gb:
        # Penalties: rating-weighted, near coin-flip.
        p = 1 / (1 + 10 ** (-(ra - rb) / 600))
        return (a, ga, gb) if rng.random() < p else (b, ga, gb)
    if ga > gb:
        return (a, ga, gb)
    if gb > ga:
        return (b, ga, gb)
    return (None, ga, gb)  # group-stage draw


def _poisson(lam, rng):
    # Knuth's algorithm.
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def _sim_group(matches, teams, ratings, rng):
    """Fill in unplayed matches, return ordered standings."""
    sim = []
    for m in matches:
        final = (m.get("home_goals") is not None
                 and m.get("away_goals") is not None and not m.get("live"))
        if final:
            sim.append(m)
        else:
            winner, hg, ag = _sim_match(m["home"], m["away"], ratings, False, rng)
            mm = dict(m); mm["home_goals"] = hg; mm["away_goals"] = ag
            sim.append(mm)
    from standings import compute_group
    return compute_group(sim, teams)


def run(matches_by_group, teams_by_group, n=10000, seed_ratings=None, rng=None):
    """Run n simulations. Return per-team probabilities (0-1) of reaching
    each stage and winning the title."""
    rng = rng or random.Random(12345)
    base_standings = all_groups(matches_by_group, teams_by_group)
    ratings = infer_ratings(base_standings, seed_ratings)

    all_teams = [r["team"] for t in base_standings.values() for r in t]
    counts = {t: defaultdict(int) for t in all_teams}
    # Per-R32-slot occupant tallies, for bracket predictions.
    slot_counts = {mn: {"home": defaultdict(int), "away": defaultdict(int)}
                   for mn, _, _ in B.ROUND_OF_32}

    for _ in range(n):
        standings = {g: _sim_group(matches_by_group[g], teams_by_group.get(g),
                                    ratings, rng)
                     for g in matches_by_group}

        slots = {}
        for g, table in standings.items():
            slots[f"1{g}"] = table[0]["team"]
            slots[f"2{g}"] = table[1]["team"]
            counts[table[0]["team"]]["group_winner"] += 1
            for r in table[:2]:
                counts[r["team"]]["r32"] += 1

        thirds = rank_third_places(standings)[:8]
        mapping = B.assign_third_places([t["group"] for t in thirds])
        by_group = {t["group"]: t["team"] for t in thirds}
        third_team = {mn: by_group[grp] for mn, grp in mapping.items()}
        for t in thirds:
            counts[t["team"]]["r32"] += 1

        # Resolve R32 participants.
        winners = {}
        for match_no, hs, as_ in B.ROUND_OF_32:
            home = slots[hs]
            away = third_team[match_no] if as_.startswith("3?") else slots[as_]
            slot_counts[match_no]["home"][home] += 1
            slot_counts[match_no]["away"][away] += 1
            w, _, _ = _sim_match(home, away, ratings, True, rng)
            winners[match_no] = w
            counts[w]["r16"] += 1

        for rnd, label in [(B.ROUND_OF_16, "qf"), (B.QUARTER_FINALS, "sf"),
                           (B.SEMI_FINALS, "final")]:
            for match_no, a, b in rnd:
                w, _, _ = _sim_match(winners[a], winners[b], ratings, True, rng)
                winners[match_no] = w
                counts[w][label] += 1

        mn, a, b = B.FINAL
        champ, _, _ = _sim_match(winners[a], winners[b], ratings, True, rng)
        winners[mn] = champ
        counts[champ]["champion"] += 1

    stages = ["r32", "r16", "qf", "sf", "final", "champion", "group_winner"]
    probs = {t: {s: counts[t][s] / n for s in stages} for t in all_teams}

    def _modal(tally):
        team, c = max(tally.items(), key=lambda kv: kv[1])
        p = c / n
        return {"team": team, "prob": p, "certain": p >= 0.9995}

    slot_pred = {mn: {"home": _modal(sc["home"]), "away": _modal(sc["away"])}
                 for mn, sc in slot_counts.items()}
    return probs, ratings, slot_pred
