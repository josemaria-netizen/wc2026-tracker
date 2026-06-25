"""Real-world strength priors for every team in the 2026 draw.

These are World Football Elo ratings (eloratings.net scale), captured June 2026.
They are the model's *prior* — the simulation then nudges each team up or down
by replaying the actual group-stage results as Elo updates (see
``simulate.infer_ratings``). This module is the single source of truth for team
strength and is used for BOTH live and seed data, so live mode no longer falls
back to a flat 1500 for everyone.

Host advantage: the 2026 tournament is played in the USA, Mexico and Canada, so
those three sides get a documented home-field bump (``HOST_BONUS`` Elo points)
folded into their prior. eloratings.net itself values home advantage at ~100
points per match; ~75 is a deliberately conservative tournament-wide figure.
"""

# World Football Elo ratings, eloratings.net scale, June 2026.
ELO = {
    "Spain": 2171, "Argentina": 2113, "France": 2063, "England": 2042,
    "Colombia": 1998, "Brazil": 1979, "Portugal": 1976, "Netherlands": 1959,
    "Croatia": 1933, "Ecuador": 1933, "Norway": 1922, "Germany": 1910,
    "Switzerland": 1897, "Uruguay": 1890, "Japan": 1879, "Senegal": 1869,
    "Denmark": 1864, "Italy": 1859, "Belgium": 1849, "Mexico": 1834,
    "Austria": 1818, "Morocco": 1806, "Canada": 1806, "Scotland": 1790,
    "South Korea": 1784, "Australia": 1774, "Iran": 1754, "United States": 1747,
    "Panama": 1743, "Nigeria": 1739, "Poland": 1735, "Uzbekistan": 1735,
    "Algeria": 1728, "Wales": 1715, "Jordan": 1691, "Bolivia": 1665,
    "Egypt": 1660, "Ivory Coast": 1637, "Costa Rica": 1632, "Tunisia": 1614,
    "Cameroon": 1606, "Saudi Arabia": 1592, "New Zealand": 1586, "Honduras": 1567,
    "Haiti": 1542, "Ghana": 1509, "Curacao": 1467, "Qatar": 1427,
}

# Name variants other providers use -> our canonical key in ELO.
ALIASES = {
    "USA": "United States", "United States of America": "United States",
    "Korea Republic": "South Korea", "Republic of Korea": "South Korea",
    "IR Iran": "Iran", "Iran (Islamic Republic of)": "Iran",
    "Côte d'Ivoire": "Ivory Coast", "Cote d'Ivoire": "Ivory Coast",
    "Curaçao": "Curacao",
}

# 2026 co-hosts get a tournament-wide home-field bump.
HOSTS = {"United States", "Mexico", "Canada"}
HOST_BONUS = 75
DEFAULT_PRIOR = 1500.0


def canonical(name):
    """Resolve a provider's team name to our canonical ELO key."""
    return ALIASES.get(name, name)


def prior(name):
    """Prior strength for a team: its real Elo plus a host bump if applicable.
    Unknown teams fall back to a neutral 1500."""
    key = canonical(name)
    base = ELO.get(key, DEFAULT_PRIOR)
    return base + (HOST_BONUS if key in HOSTS else 0)


def is_host(name):
    return canonical(name) in HOSTS


def build_priors(matches_by_group, override=None):
    """Prior rating for every team appearing in the draw.

    ``override`` (e.g. a hand-tuned ``seed_ratings`` block) wins where present
    and is taken as an absolute value (no host bump added on top)."""
    override = override or {}
    out = {}
    for matches in matches_by_group.values():
        for m in matches:
            for team in (m["home"], m["away"]):
                if team in out:
                    continue
                out[team] = float(override[team]) if team in override else prior(team)
    return out
