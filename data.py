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


# In-play status codes. API-Football short codes + football-data statuses.
LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE",
                 "IN_PLAY", "PAUSED"}


def _round_robin(teams):
    """6 matches for a 4-team group, all goals None."""
    return [{"home": a, "away": b, "home_goals": None, "away_goals": None,
             "scorers": [], "live": False, "elapsed": None}
            for a, b in combinations(teams, 2)]


def _apply_results(matches, results):
    """Overlay played scores (and scorers) onto the fixture list, matching
    either orientation."""
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
        if m:
            m["scorers"] = r.get("scorers", [])
            m["live"] = r.get("live", False)
            m["elapsed"] = r.get("elapsed")


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
        # Each group can return TOTAL/HOME/AWAY variants; keep only TOTAL.
        if s.get("type") and s.get("type") != "TOTAL":
            continue
        grp = s.get("group", "") or ""  # e.g. "GROUP_A"
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
        # Goal-scorer events are only present on paid tiers; default to [].
        scorers = []
        for g in mtch.get("goals", []) or []:
            scorers.append({
                "team": (g.get("team") or {}).get("name", ""),
                "player": (g.get("scorer") or {}).get("name", "Unknown"),
                "minute": g.get("minute"),
            })
        results_by_group.setdefault(letter, []).append({
            "group": letter,
            "home": mtch["homeTeam"]["name"],
            "away": mtch["awayTeam"]["name"],
            "home_goals": ft.get("home"),
            "away_goals": ft.get("away"),
            "scorers": scorers,
            "live": mtch.get("status") in LIVE_STATUSES,
            "elapsed": mtch.get("minute"),
        })

    # Trust live data only when the full 12-group / 4-team draw is published;
    # anything partial would break the bracket, so fall back to the seed.
    if len(teams_by_group) != 12 or any(len(t) != 4 for t in teams_by_group.values()):
        raise RuntimeError(
            f"WC live data incomplete ({len(teams_by_group)} groups); "
            "using seed")

    matches_by_group = {}
    for letter, teams in teams_by_group.items():
        matches_by_group[letter] = _round_robin(teams)
        for m in matches_by_group[letter]:
            m["group"] = letter
        _apply_results(matches_by_group[letter], results_by_group.get(letter, []))
    return matches_by_group, teams_by_group, None


def _af_headers(key, host):
    """Auth headers for API-Football: direct (api-sports.io) or via RapidAPI."""
    if host.endswith("api-sports.io"):
        return {"x-apisports-key": key}
    return {"x-rapidapi-key": key, "x-rapidapi-host": host}


def from_api_football(key=None, host=None, league=1, season=2026):
    """Fetch live group results from API-Football (api-sports.io).

    Returns the same triple as load_seed(). Raises on HTTP errors or when the
    full 12-group draw isn't published yet, so the caller can fall back.
    """
    key = key or os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise RuntimeError("no API_FOOTBALL_KEY set")
    host = host or os.environ.get("API_FOOTBALL_HOST", "v3.football.api-sports.io")
    base = f"https://{host}"
    headers = _af_headers(key, host)
    params = {"league": league, "season": season}

    # Standings -> group -> teams. Response: [{league:{standings:[[row,...],...]}}]
    st = requests.get(f"{base}/standings", headers=headers, params=params,
                      timeout=20)
    st.raise_for_status()
    resp = st.json().get("response", [])
    teams_by_group, team_group = {}, {}
    if resp:
        valid = set("ABCDEFGHIJKL")
        for group_table in resp[0].get("league", {}).get("standings", []):
            for row in group_table:
                # Real groups are labelled "Group A".."Group L"; the API also
                # returns a "Group Stage" table (third-place ranking) we skip.
                parts = (row.get("group", "") or "").split()
                if len(parts) != 2 or parts[0] != "Group" or parts[1] not in valid:
                    continue
                letter = parts[1]
                name = row["team"]["name"]
                teams_by_group.setdefault(letter, []).append(name)
                team_group[name] = letter

    if len(teams_by_group) != 12 or any(len(t) != 4 for t in teams_by_group.values()):
        raise RuntimeError(
            f"API-Football WC draw incomplete ({len(teams_by_group)} groups); "
            "using fallback")

    # Fixtures -> played results, mapped to a group via the home team.
    fx = requests.get(f"{base}/fixtures", headers=headers, params=params,
                      timeout=20)
    fx.raise_for_status()
    results_by_group = {}
    for f in fx.json().get("response", []):
        if "Group" not in (f.get("league", {}).get("round", "") or ""):
            continue
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        gh, ga = f["goals"]["home"], f["goals"]["away"]
        if gh is None or ga is None:
            continue  # not kicked off yet
        status = (f.get("fixture", {}).get("status", {}) or {})
        letter = team_group.get(home) or team_group.get(away)
        if not letter:
            continue
        results_by_group.setdefault(letter, []).append({
            "group": letter, "home": home, "away": away,
            "home_goals": gh, "away_goals": ga, "scorers": [],
            "live": status.get("short") in LIVE_STATUSES,
            "elapsed": status.get("elapsed"),
        })

    matches_by_group = {}
    for letter, teams in teams_by_group.items():
        matches_by_group[letter] = _round_robin(teams)
        for m in matches_by_group[letter]:
            m["group"] = letter
        _apply_results(matches_by_group[letter], results_by_group.get(letter, []))
    return matches_by_group, teams_by_group, None


def _af_top_scorers(key, host, league, season, limit):
    base = f"https://{host}"
    resp = requests.get(f"{base}/players/topscorers",
                        headers=_af_headers(key, host),
                        params={"league": league, "season": season}, timeout=20)
    resp.raise_for_status()
    out = []
    for s in resp.json().get("response", [])[:limit]:
        stats = (s.get("statistics") or [{}])[0]
        out.append({
            "player": (s.get("player") or {}).get("name", "Unknown"),
            "team": (stats.get("team") or {}).get("name", ""),
            "goals": (stats.get("goals") or {}).get("total") or 0,
            "assists": (stats.get("goals") or {}).get("assists") or 0,
        })
    return out


def top_scorers(competition="WC", limit=20):
    """Tournament top scorers from whichever live provider is configured.
    Returns [{player, team, goals, assists}] or [] if unavailable."""
    af_key = os.environ.get("API_FOOTBALL_KEY")
    if af_key:
        try:
            host = os.environ.get("API_FOOTBALL_HOST", "v3.football.api-sports.io")
            return _af_top_scorers(af_key, host, 1, 2026, limit)
        except Exception:  # noqa: BLE001
            pass
    fd_token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if fd_token:
        try:
            resp = requests.get(
                f"https://api.football-data.org/v4/competitions/{competition}/scorers",
                headers={"X-Auth-Token": fd_token},
                params={"limit": limit}, timeout=20)
            resp.raise_for_status()
            return [{
                "player": (s.get("player") or {}).get("name", "Unknown"),
                "team": (s.get("team") or {}).get("name", ""),
                "goals": s.get("goals") or 0,
                "assists": s.get("assists") or 0,
            } for s in resp.json().get("scorers", [])]
        except Exception:  # noqa: BLE001
            pass
    return []


def load(prefer_live=True):
    """Try live providers in order (API-Football, then football-data.org),
    fall back to the seed. Returns (triple, source_label)."""
    if prefer_live:
        if os.environ.get("API_FOOTBALL_KEY"):
            try:
                return from_api_football(), "API-Football (live)"
            except Exception as e:  # noqa: BLE001
                print(f"[data] API-Football fetch failed ({e})")
        if os.environ.get("FOOTBALL_DATA_TOKEN"):
            try:
                return from_football_data(), "football-data.org (live)"
            except Exception as e:  # noqa: BLE001
                print(f"[data] football-data fetch failed ({e})")
    return load_seed(), "seed_data.json"
