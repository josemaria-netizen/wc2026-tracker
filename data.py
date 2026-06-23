"""
Data layer. Two sources:

  1. football-data.org  -> live results (set FOOTBALL_DATA_TOKEN). Free tier;
     World Cup competition code "WC".
  2. seed_data.json     -> offline demo / manual editing. Defines the 12
     groups, any played results, and optional strength ratings.

Both normalise to the same shape consumed by the rest of the app:

  matches_by_group : {group: [match, ...]}   round-robin, 6 matches/group
  teams_by_group   : {group: [team, ...]}
  seed_ratings     : {team: rating} or None

A `match` is {"group","home","away","home_goals","away_goals"} with goals
None until played.
"""

import json
import os
from itertools import combinations

import requests


def _round_robin(teams):
    """6 matches for a 4-team group, all goals None."""
    return [{"home": a, "away": b, "home_goals": None, "away_goals": None}
            for a, b in combinations(teams, 2)]


def _apply_results(matches, results):
    """Overlay played scores onto the fixture list, matching either orientation."""
    index = {}
    for m in matches:
        index[(m["home"], m["away"])] = m
    for r in results:
        m = index.get((r["home"], r["away"]))
        if m:
            m["home_goals"] = r["home_goals"]
            m["away_goals"] = r["away_goals"]
        else:
            # Result stored with reversed orientation: flip the score.
            m = index.get((r["away"], r["home"]))
            if m:
                m["home_goals"] = r["away_goals"]
                m["away_goals"] = r["home_goals"]


def load_seed(path="seed_data.json"):
    with open(path) as f:
        data = json.load(f)
    groups = data["groups"]
    matches_by_group, teams_by_group = {}, {}
    for g, teams in groups.items():
        teams_by_group[g] = teams
        matches_by_group[g] = _round_robin(teams)
        for m in matches_by_group[g]:
            m["group"] = g
    by_group_results = {}
    for r in data.get("results", []):
        by_group_results.setdefault(r["group"], []).append(r)
    for g, rs in by_group_results.items():
        _apply_results(matches_by_group[g], rs)
    return matches_by_group, teams_by_group, data.get("seed_ratings")


def from_football_data(token=None, competition="WC"):
    """Fetch live group-stage results from football-data.org.

    Returns the same triple as load_seed(). Raises on HTTP/auth errors so the
    caller can fall back to the seed.
    """
    token = token or os.environ.get("FOOTBALL_DATA_TOKEN")
    if not token:
        raise RuntimeError("no FOOTBALL_DATA_TOKEN set")
    headers = {"X-Auth-Token": token}
    base = "https://api.football-data.org/v4"

    standings = requests.get(f"{base}/competitions/{competition}/standings",
                             headers=headers, timeout=20)
    standings.raise_for_status()
    teams_by_group = {}
    for s in standings.json().get("standings", []):
        grp = s.get("group", "")  # e.g. "GROUP_A"
        if not grp.startswith("GROUP_"):
            continue
        letter = grp.split("_")[-1]
        teams_by_group[letter] = [row["team"]["name"] for row in s["table"]]

    matches = requests.get(f"{base}/competitions/{competition}/matches",
                           headers=headers, timeout=20)
    matches.raise_for_status()
    results_by_group = {}
    for mtch in matches.json().get("matches", []):
        grp = (mtch.get("group") or "")
        if not grp.startswith("GROUP_"):
            continue
        letter = grp.split("_")[-1]
        ft = mtch.get("score", {}).get("fullTime", {})
        results_by_group.setdefault(letter, []).append({
            "group": letter,
            "home": mtch["homeTeam"]["name"],
            "away": mtch["awayTeam"]["name"],
            "home_goals": ft.get("home"),
            "away_goals": ft.get("away"),
        })

    matches_by_group = {}
    for letter, teams in teams_by_group.items():
        matches_by_group[letter] = _round_robin(teams)
        for m in matches_by_group[letter]:
            m["group"] = letter
        _apply_results(matches_by_group[letter], results_by_group.get(letter, []))
    return matches_by_group, teams_by_group, None


def load(prefer_live=True):
    """Try live data, fall back to seed. Returns (triple, source_label)."""
    if prefer_live and os.environ.get("FOOTBALL_DATA_TOKEN"):
        try:
            return from_football_data(), "football-data.org (live)"
        except Exception as e:  # noqa: BLE001 - any failure -> seed fallback
            print(f"[data] live fetch failed ({e}); using seed")
    return load_seed(), "seed_data.json"
