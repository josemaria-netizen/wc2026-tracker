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

import data as D
import project as P
from flags import flag
from simulate import run as run_sim
from standings import all_groups, rank_third_places
import bracket as B

st.set_page_config(page_title="World Cup 2026 Tracker", page_icon="⚽",
                   layout="wide")

STAGE_LABELS = [
    ("r32", "R32"), ("r16", "R16"), ("qf", "QF"),
    ("sf", "SF"), ("final", "Final"), ("champion", "Champion"),
]


@st.cache_data(ttl=120)
def load_data(prefer_live):
    return D.load(prefer_live=prefer_live)


@st.cache_data(ttl=120, show_spinner="Simulating tournament…")
def simulate(matches_by_group, teams_by_group, n, seed_ratings):
    return run_sim(matches_by_group, teams_by_group, n=n,
                   seed_ratings=seed_ratings)


def render_match(m):
    """Render one match: flags + names + score, with goalscorers underneath."""
    home, away = m["home"], m["away"]
    hg, ag = m.get("home_goals"), m.get("away_goals")
    fh, fa = flag(home), flag(away)
    played = hg is not None and ag is not None
    if played:
        st.markdown(
            f"<div style='font-size:1.15rem;'>{fh} <b>{home}</b> "
            f"<b>{hg} – {ag}</b> <b>{away}</b> {fa}</div>",
            unsafe_allow_html=True)
        scorers = m.get("scorers") or []
        if scorers:
            home_g = [s for s in scorers if s["team"] == home]
            away_g = [s for s in scorers if s["team"] == away]

            def fmt(lst):
                return "  ·  ".join(
                    f"⚽ {s['player']}"
                    + (f" {s['minute']}'" if s.get("minute") is not None else "")
                    for s in lst) or "—"
            c1, c2 = st.columns(2)
            c1.caption(fmt(home_g))
            c2.caption(fmt(away_g))
        else:
            st.caption("Goalscorers not available for this match.")
    else:
        st.markdown(
            f"<div style='font-size:1.15rem; color:#888;'>{fh} {home} "
            f"<i>vs</i> {away} {fa} &nbsp;·&nbsp; <i>to be played</i></div>",
            unsafe_allow_html=True)
    st.write("")


def _bridge_secrets():
    """Make the token in Streamlit secrets visible to the data layer (which
    reads os.environ). Safe when no secrets file exists."""
    try:
        if "FOOTBALL_DATA_TOKEN" in st.secrets:
            os.environ["FOOTBALL_DATA_TOKEN"] = st.secrets["FOOTBALL_DATA_TOKEN"]
    except Exception:  # noqa: BLE001 - no secrets.toml present
        pass


def main():
    _bridge_secrets()
    st.title("⚽ World Cup 2026 — Live Tracker & Knockout Predictor")

    with st.sidebar:
        st.header("Settings")
        prefer_live = st.toggle("Use live data (football-data.org)", value=True,
                                help="Falls back to seed_data.json if no API "
                                     "token or the fetch fails.")
        n_sims = st.select_slider("Simulations", [2000, 5000, 10000, 25000],
                                  value=10000)
        st.caption("Set FOOTBALL_DATA_TOKEN in the environment / Streamlit "
                   "secrets for live results.")

    (matches_by_group, teams_by_group, seed_ratings), source = \
        load_data(prefer_live)
    standings = all_groups(matches_by_group, teams_by_group)
    st.caption(f"Data source: **{source}** · {len(standings)} groups")

    tab_home, tab_matches, tab_groups, tab_bracket, tab_odds = st.tabs(
        ["💚 Hey Chunch", "⚽ Matches", "📊 Group standings",
         "🏆 Projected bracket", "🎲 Knockout odds"])

    # --- Landing page ------------------------------------------------------
    with tab_home:
        st.markdown(
            """
            <div style="text-align:center; padding: 3rem 1rem;">
              <div style="font-size:5rem; line-height:1;">⚽💚</div>
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
        st.caption("Games by group — flags, scores, and goalscorers. "
                   "Matches without a score are still to be played.")
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
                st.subheader(f"Group {g}")
                for m in matches_by_group[g]:
                    render_match(m)
                st.divider()

    # --- Group standings ---------------------------------------------------
    with tab_groups:
        cols = st.columns(3)
        for i, g in enumerate(sorted(standings)):
            with cols[i % 3]:
                st.subheader(f"Group {g}")
                df = pd.DataFrame(standings[g])[
                    ["rank", "team", "played", "won", "drawn", "lost",
                     "gf", "ga", "gd", "points"]]
                df.columns = ["#", "Team", "P", "W", "D", "L", "GF", "GA",
                              "GD", "Pts"]
                st.dataframe(df, hide_index=True, use_container_width=True)

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
        st.subheader("Round of 32")
        r32 = P.project_round_of_32(standings)
        any_tbd = any(m["home"] == "TBD" or m["away"] == "TBD" for m in r32)
        if any_tbd:
            st.info("Some slots show **TBD** — they resolve once every group "
                    "finishes its three matches (third-place seeding needs all "
                    "12 groups complete).")
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
        st.caption(f"{n_sims:,} Monte-Carlo simulations · Poisson goal model, "
                   "ratings blended from seed values and live form.")
        probs, ratings = simulate(matches_by_group, teams_by_group, n_sims,
                                  seed_ratings)
        rows = []
        for team, p in probs.items():
            rows.append({"Team": team, "Rating": round(ratings.get(team, 1500)),
                         **{label: p[key] for key, label in STAGE_LABELS}})
        df = pd.DataFrame(rows).sort_values(
            ["Champion", "Final", "SF"], ascending=False)
        styled = df.style.format(
            {label: "{:.1%}" for _, label in STAGE_LABELS})
        st.dataframe(styled, hide_index=True, use_container_width=True,
                     height=560)
        st.bar_chart(df.set_index("Team")["Champion"].head(12))


if __name__ == "__main__":
    main()
