"""
2026 World Cup live tracker + knockout predictor (Streamlit).

  - Pulls live group results (football-data.org) or an editable seed file.
  - Computes group standings with FIFA tiebreakers.
  - Projects the Round-of-32 bracket deterministically once groups decide.
  - Monte-Carlo simulates the rest for advancement / title odds.

Run locally:   streamlit run app.py
Deploy:        push to GitHub, connect at share.streamlit.io
"""

import os

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import data as D
import project as P
from bracket_view import build_bracket_html
from flags import flag
import ratings as R
import market as M

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:  # noqa: BLE001 - optional dependency
    st_autorefresh = None
from simulate import run as run_sim
from standings import all_groups, rank_third_places
import bracket as B

st.set_page_config(page_title="World Cup 2026 Tracker", page_icon="⚽",
                   layout="wide")

STAGE_LABELS = [
    ("r32", "R32"), ("r16", "R16"), ("qf", "QF"),
    ("sf", "SF"), ("final", "Final"), ("champion", "Champion"),
]


@st.cache_data(ttl=60)
def load_data(prefer_live):
    return D.load(prefer_live=prefer_live)


# Note: name is versioned (…_v3) so a redeploy never reuses an older cached
# return shape from @st.cache_data. Bump the suffix if the args/return change.
@st.cache_data(ttl=600, show_spinner="Simulating tournament…")
def simulate_v3(matches_by_group, teams_by_group, n, priors):
    return run_sim(matches_by_group, teams_by_group, n=n, priors=priors)


def _name_cell(name, flag_html, align, won):
    """One team cell: name + flag, right- or left-aligned, bold if winner."""
    weight = "600" if won else "400"
    color = "#e6ebf5" if won else "#aab3c4"
    parts = ([f"<span style='font-weight:{weight};color:{color};overflow:hidden;"
              f"text-overflow:ellipsis;white-space:nowrap;'>{name}</span>",
              f"<span>{flag_html}</span>"])
    if align == "left":
        parts = parts[::-1]
    return (f"<div style='flex:1;display:flex;align-items:center;gap:7px;"
            f"justify-content:flex-{'end' if align == 'right' else 'start'};"
            f"min-width:0;'>{''.join(parts)}</div>")


def match_card_html(m):
    """One clean, aligned match row: home | score chip | away."""
    home, away = m["home"], m["away"]
    hg, ag = m.get("home_goals"), m.get("away_goals")
    played = hg is not None and ag is not None
    home_won = played and hg > ag
    away_won = played and ag > hg

    live = bool(m.get("live"))
    if played:
        bg = "#b91c1c" if live else "#222c3e"
        chip = (f"<span style='background:{bg};border-radius:6px;padding:"
                f"3px 10px;font-weight:700;color:#fff;font-variant-numeric:"
                f"tabular-nums;'>{hg}&nbsp;–&nbsp;{ag}</span>")
    else:
        chip = "<span style='color:#5b6477;font-size:0.85em;'>vs</span>"

    card = (f"<div style='display:flex;align-items:center;gap:8px;padding:"
            f"7px 4px;'>"
            f"{_name_cell(home, flag(home), 'right', home_won)}"
            f"<div style='flex:0 0 64px;text-align:center;'>{chip}</div>"
            f"{_name_cell(away, flag(away), 'left', away_won)}</div>")

    if live:
        el = f" · {m['elapsed']}'" if m.get("elapsed") else ""
        card += (f"<div style='text-align:center;font-size:0.66em;color:#ef4444;"
                 f"font-weight:700;letter-spacing:0.6px;padding-bottom:4px;'>"
                 f"🔴 LIVE{el}</div>")

    # Goalscorers only when the provider supplied them (kept compact).
    scorers = m.get("scorers") or []
    if scorers:
        def fmt(team):
            return " · ".join(
                f"{s['player']}"
                + (f" {s['minute']}'" if s.get("minute") is not None else "")
                for s in scorers if s["team"] == team) or "&nbsp;"
        card += (f"<div style='display:flex;font-size:0.72em;color:#7c8699;"
                 f"padding:0 4px 6px;'><div style='flex:1;text-align:right;'>⚽ "
                 f"{fmt(home)}</div><div style='flex:0 0 64px;'></div>"
                 f"<div style='flex:1;text-align:left;'>{fmt(away)} ⚽</div></div>")
    return card


def _bridge_secrets():
    """Make the token in Streamlit secrets visible to the data layer (which
    reads os.environ). Safe when no secrets file exists."""
    try:
        for k in ("API_FOOTBALL_KEY", "API_FOOTBALL_HOST",
                  "FOOTBALL_DATA_TOKEN"):
            if k in st.secrets:
                os.environ[k] = str(st.secrets[k])
    except Exception:  # noqa: BLE001 - no secrets.toml present
        pass


def main():
    _bridge_secrets()
    st.title("⚽ World Cup 2026 — Live Tracker & Knockout Predictor")

    with st.sidebar:
        st.header("Settings")
        prefer_live = st.toggle("Use live data", value=True,
                                help="Falls back to seed_data.json if no API "
                                     "key or the fetch fails.")
        n_sims = st.select_slider("Simulations", [2000, 5000, 10000, 25000],
                                  value=10000)
        market_pull = st.slider(
            "Betting-market influence", 0, 100, 50, 10,
            format="%d%%",
            help="How far to pull team ratings toward the bookmakers' "
                 "title-winner odds. 0% = pure Elo model; 100% = trust the "
                 "market. Flows through every round of the simulation.") / 100.0

        st.divider()
        auto = st.toggle("🔄 Auto-refresh", value=False,
                         help="Periodically reload to pull the latest scores.")
        if auto:
            secs = st.select_slider("Every", [30, 60, 120, 300], value=60,
                                    format_func=lambda s: f"{s}s")
            if st_autorefresh:
                st_autorefresh(interval=secs * 1000, key="live_refresh")
            else:
                st.caption("`streamlit-autorefresh` not installed — add it to "
                           "requirements.txt to enable.")
        st.caption("Set API_FOOTBALL_KEY (or FOOTBALL_DATA_TOKEN) in Streamlit "
                   "secrets for live results.")

    (matches_by_group, teams_by_group, _seed_ratings), source = \
        load_data(prefer_live)
    standings = all_groups(matches_by_group, teams_by_group)
    # Real-world Elo priors for every team in the draw — the single source of
    # truth for team strength, used for live AND seed data. (seed_ratings is
    # ignored: ratings.py supersedes the old hand-tuned block.) Then pull the
    # ratings toward the betting market by the chosen amount.
    priors = M.blend_priors(R.build_priors(matches_by_group), market_pull)
    st.caption(f"Data source: **{source}** · {len(standings)} groups")

    tab_home, tab_matches, tab_groups, tab_bracket, tab_odds = st.tabs(
        ["🦙 Hey Chunch", "⚽ Matches", "📊 Group standings",
         "🏆 Projected bracket", "🎲 Knockout odds"])

    # --- Landing page ------------------------------------------------------
    with tab_home:
        st.markdown(
            """
            <div style="text-align:center; padding: 3rem 1rem;">
              <div style="font-size:5rem; line-height:1;">⚽🦙</div>
              <h1 style="font-size:3.5rem; margin:1rem 0 0.5rem;">Hey Chunch!</h1>
              <p style="font-size:1.4rem; color:#a3a3a3; margin:0;">
                Welcome to your very own World Cup tracker.
              </p>
              <p style="font-size:1.1rem; color:#8b8b8b; max-width:640px;
                        margin:1.5rem auto 0;">
                I built this just for you. Flip through the tabs to see the live
                group standings, the projected knockout bracket, and each team's
                odds of going all the way. 🏆
              </p>
              <p style="font-size:1rem; color:#22c55e; margin-top:2rem;">
                Made with love ❤️
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --- Matches -----------------------------------------------------------
    with tab_matches:
        st.caption("Games by group · scores update live · played matches "
                   "shown first.")
        scorers = D.top_scorers()
        if scorers:
            st.subheader("👟 Golden Boot race — top scorers")
            sdf = pd.DataFrame(scorers)
            sdf.insert(0, "#", range(1, len(sdf) + 1))
            sdf["player"] = [f"{flag(r['team'])} {r['player']}"
                             for r in scorers]
            sdf = sdf[["#", "player", "team", "goals", "assists"]]
            sdf.columns = ["#", "Player", "Team", "Goals", "Assists"]
            st.dataframe(sdf, hide_index=True, use_container_width=True)
            st.divider()

        cols = st.columns(2)
        for i, g in enumerate(sorted(matches_by_group)):
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"##### Group {g}")
                    # Played matches first, then upcoming.
                    ordered = sorted(
                        matches_by_group[g],
                        key=lambda m: m.get("home_goals") is None)
                    st.markdown(
                        "".join(match_card_html(m) for m in ordered),
                        unsafe_allow_html=True)

    # --- Group standings ---------------------------------------------------
    with tab_groups:
        cols = st.columns(3)
        for i, g in enumerate(sorted(standings)):
            with cols[i % 3]:
                st.subheader(f"Group {g}")
                df = pd.DataFrame(standings[g])[
                    ["rank", "team", "played", "won", "drawn", "lost",
                     "gf", "ga", "gd", "points"]]
                df["team"] = [f"{flag(t)} {t}" for t in df["team"]]
                df.columns = ["#", "Team", "P", "W", "D", "L", "GF", "GA",
                              "GD", "Pts"]
                st.dataframe(df, hide_index=True, use_container_width=True,
                             column_config={
                                 "Pts": st.column_config.NumberColumn(
                                     "Pts", help="Points", width="small")})

        st.subheader("Best third-placed teams (top 8 advance)")
        thirds = rank_third_places(standings)
        if thirds:
            tdf = pd.DataFrame(thirds)[
                ["third_rank", "group", "team", "points", "gd", "gf"]]
            tdf.columns = ["Rank", "Grp", "Team", "Pts", "GD", "GF"]
            tdf["Qualifies"] = ["✅" if r <= 8 else "" for r in tdf["Rank"]]
            st.dataframe(tdf, hide_index=True, use_container_width=True)

    # --- Projected bracket -------------------------------------------------
    with tab_bracket:
        st.subheader("Knockout bracket")
        r32 = P.project_round_of_32(standings)
        can_predict = (len(standings) == 12
                       and all(len(t) >= 4 for t in standings.values()))
        r32_pred = None
        if can_predict:
            try:
                _, _, r32_pred = simulate_v3(matches_by_group, teams_by_group,
                                             n_sims, priors)
            except Exception:  # noqa: BLE001 - fall back to plain bracket
                r32_pred = None
        if r32_pred is None:
            def _entry(name):
                return (None if name == "TBD"
                        else {"team": name, "prob": None, "certain": False})
            r32_pred = {m["match"]: {"home": _entry(m["home"]),
                                     "away": _entry(m["away"])} for m in r32}
        st.caption("Solid = already mathematically certain · faded with a % = "
                   "most likely team to land there (Monte-Carlo) · later rounds "
                   "show Winner M## until those matches exist.")
        html, height = build_bracket_html(r32_pred)
        components.html(html, height=height, scrolling=True)

        with st.expander("Round of 32 — table view"):
            rows = [{"Match": m["match"],
                     "Home": m["home"], "": "vs", "Away": m["away"],
                     "Bracket slot": f'{m["home_slot"]} v {m["away_slot"]}'}
                    for m in r32]
            st.dataframe(pd.DataFrame(rows), hide_index=True,
                         use_container_width=True)
        with st.expander("How third-place teams are slotted"):
            st.markdown(
                "Each `3?` slot is restricted to a fixed set of 5 groups. Once "
                "the 8 best third-placed teams are known, each is assigned to a "
                "slot satisfying those constraints (FIFA Annex C). Before that, "
                "the eligible groups are shown in the bracket-slot column.")

    # --- Knockout odds -----------------------------------------------------
    with tab_odds:
        st.subheader("Advancement & title odds")
        st.caption(f"{n_sims:,} Monte-Carlo simulations · Poisson goal model · "
                   "real World-Football-Elo priors, updated by live results · "
                   f"ratings pulled {market_pull:.0%} toward the betting market · "
                   "🏠 = host (home-field boost).")
        if len(standings) != 12 or any(len(t) < 4 for t in standings.values()):
            st.warning("Title odds need all 12 groups of 4 teams. The current "
                       "data source doesn't have the full draw yet, so the "
                       "simulation is paused. (Standings, matches, and the "
                       "bracket above still work.)")
            st.stop()
        try:
            probs, ratings, _ = simulate_v3(matches_by_group, teams_by_group,
                                            n_sims, priors)
        except Exception:  # noqa: BLE001
            st.warning("Odds are temporarily unavailable — try reloading.")
            st.stop()
        rows = []
        for team, p in probs.items():
            label_team = f"🏠 {team}" if R.is_host(team) else team
            rows.append({"Team": label_team,
                         "Rating": round(ratings.get(team, 1500)),
                         **{label: p[key] for key, label in STAGE_LABELS},
                         "Mkt": M.implied_prob(team)})
        df = pd.DataFrame(rows).sort_values(
            ["Champion", "Final", "SF"], ascending=False)
        pct_cols = [label for _, label in STAGE_LABELS] + ["Mkt"]
        styled = df.style.format(
            {c: (lambda v: "—" if pd.isna(v) else f"{v:.1%}") for c in pct_cols})
        st.dataframe(styled, hide_index=True, use_container_width=True, height=560,
                     column_config={"Mkt": st.column_config.Column(
                         "Mkt", help="Bookmakers' devigged title odds — the "
                         "real-money market, for comparison with the model's "
                         "Champion column.")})
        st.bar_chart(df.set_index("Team")["Champion"].head(12))

        with st.expander("How these odds are built"):
            st.markdown(
                "- **Real strength priors.** Every team starts from its "
                "World-Football-Elo rating (eloratings.net scale), not a flat "
                "average — so a powerhouse and a minnow never look alike.\n"
                "- **Opponent-weighted form.** Played group games update those "
                "ratings Elo-style: beating a strong side moves you more than "
                "thrashing a weak one. Live (in-progress) games don't count "
                "until final.\n"
                "- **Host boost (🏠).** USA, Mexico and Canada carry a "
                "home-field bump folded into their rating.\n"
                "- **Betting-market pull.** Ratings are nudged toward the "
                "bookmakers' title odds by the sidebar slider, so real-money "
                "opinion flows through every round. The **Mkt** column shows "
                "those odds (de-vigged) next to the model's Champion %.\n"
                "- **Calibrated goal model.** The rating gap maps to expected "
                "goals so a match win probability tracks the Elo formula "
                "`1/(1+10^(-gap/400))`.\n"
                f"- **{n_sims:,} simulations.** Each percentage is the share of "
                "simulated tournaments a team reached that round, so the "
                "numbers wiggle slightly each refresh — more sims = steadier.")


if __name__ == "__main__":
    main()
