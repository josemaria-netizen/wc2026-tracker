"""
2026 World Cup live tracker + knockout predictor (Streamlit).

  - Pulls live group results (football-data.org) or an editable seed file.
  - Computes group standings with FIFA tiebreakers.
  - Projects the Round-of-32 bracket deterministically once groups decide.
  - Monte-Carlo simulates the rest for advancement / title odds.

Run locally:   streamlit run app.py
Deploy:        push to GitHub, connect at share.streamlit.io
"""

import pandas as pd
import streamlit as st

import data as D
import project as P
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


def main():
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

    tab_groups, tab_bracket, tab_odds = st.tabs(
        ["📊 Group standings", "🏆 Projected bracket", "🎲 Knockout odds"])

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
