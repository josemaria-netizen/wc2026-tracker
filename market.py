"""Bookmaker outright-winner odds — a real-money anchor for the model.

Captured 2026-06-24 from a consensus all-48-teams title market. Stored as
fractional odds-against (profit-to-1: +450 -> 4.5, "14-1" -> 14). Used two ways:

  * a transparent "Mkt" column in the odds table, and
  * a pull on each team's strength rating toward what the market implies, so the
    betting market flows through the whole Monte-Carlo simulation rather than
    being bolted on at the end.

The pull learns the Elo<->log-odds relationship by least squares over teams that
have both a prior and a quote, then moves each quoted team a tunable fraction of
the way from its Elo prior to the market-implied rating. Outliers the market
disagrees with (e.g. a host whose rating is inflated by the home bump) get moved
the most; teams already in line barely budge.
"""

import math

import ratings as R

# Fractional odds-against to win the title (June 24 2026 consensus).
ODDS = {
    "France": 4.5, "Spain": 4.5, "England": 7, "Portugal": 7,
    "Argentina": 9, "Brazil": 9, "Germany": 14, "Netherlands": 18,
    "Belgium": 33, "Norway": 33, "United States": 33, "Colombia": 40,
    "Morocco": 40, "Mexico": 50, "Japan": 50, "Switzerland": 66,
    "Uruguay": 66, "Croatia": 80, "Senegal": 80, "Australia": 100,
    "Ecuador": 100, "Ivory Coast": 100, "Austria": 150, "Canada": 150,
    "Scotland": 150, "South Korea": 200, "Algeria": 250, "Egypt": 250,
    "Iran": 500, "Ghana": 500, "Tunisia": 750, "Jordan": 1000,
    "New Zealand": 1000, "Panama": 1000, "Qatar": 1000, "Saudi Arabia": 1000,
    "Uzbekistan": 1000, "Curacao": 2500, "Haiti": 2500,
}

# Bookmaker overround across the full 48-team market (~127%). Divided out so the
# displayed probabilities are fair. Note: this constant only scales the shown
# percentages — it cancels out of the rating regression (a shift in log-odds is
# absorbed by the fitted intercept), so the model blend is robust to it.
OVERROUND = 1.27


def implied_prob(team):
    """Devigged market probability this team wins the title, or None if the
    team has no quote. Resolves provider name variants (e.g. 'Korea Republic')."""
    o = ODDS.get(R.canonical(team))
    if o is None:
        return None
    return (1.0 / (o + 1.0)) / OVERROUND


def blend_priors(priors, weight):
    """Return priors pulled `weight` (0..1) of the way toward market-implied
    ratings. weight=0 leaves Elo untouched; weight=1 uses the market fit."""
    if weight <= 0:
        return dict(priors)
    pts = [(priors[t], math.log(p)) for t in priors
           if (p := implied_prob(t)) is not None]
    if len(pts) < 3:
        return dict(priors)  # not enough anchors to fit a line
    n = len(pts)
    mx = sum(x for _, x in pts) / n            # x = ln(market prob)
    my = sum(y for y, _ in pts) / n            # y = Elo prior
    var = sum((x - mx) ** 2 for _, x in pts)
    if var == 0:
        return dict(priors)
    b = sum((y - my) * (x - mx) for y, x in pts) / var
    a = my - b * mx
    out = dict(priors)
    for t in priors:
        p = implied_prob(t)
        if p is None:
            continue  # no quote -> keep pure Elo
        market_rating = a + b * math.log(p)
        out[t] = priors[t] * (1 - weight) + market_rating * weight
    return out
