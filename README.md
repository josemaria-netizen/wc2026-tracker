# ⚽ World Cup 2026 — Live Tracker & Knockout Predictor

A shareable Streamlit app that pulls live group-stage results, computes
standings with the official FIFA tiebreakers, projects the Round-of-32
bracket, and Monte-Carlo simulates the rest of the tournament for
advancement and title odds.

Built for the **2026 format**: 48 teams, 12 groups (A–L), top 2 of each group
plus the **8 best third-placed teams** advancing to a Round of 32, then single
elimination through to the final.

## Features

- **📊 Group standings** — points → goal difference → goals → head-to-head,
  per FIFA rules, plus the cross-group ranking of third-placed teams.
- **🏆 Projected bracket** — resolves the real R32 pairings (incl. FIFA's
  third-place allocation) as groups finish; unresolved slots show `TBD`.
- **🎲 Knockout odds** — Poisson goal model with team ratings blended from
  seed values and live form; reports R32 → Champion probabilities.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at <http://localhost:8501>. With no API token it uses
`seed_data.json` (an editable, illustrative dataset).

## Live data (football-data.org)

1. Grab a free token at <https://www.football-data.org/client/register>.
2. Export it before running:

   ```bash
   export FOOTBALL_DATA_TOKEN=your_token_here
   streamlit run app.py
   ```

The app fetches the World Cup competition (`WC`) standings + matches and falls
back to the seed file if the token is missing or the request fails.

## Deploy to Streamlit Community Cloud (free, one public URL)

1. Push this folder to a **public GitHub repo**.
2. Go to <https://share.streamlit.io> → **New app** → pick the repo and
   `app.py`.
3. Add the API token under **Advanced settings → Secrets**:

   ```toml
   FOOTBALL_DATA_TOKEN = "your_token_here"
   ```

4. Deploy → share the `*.streamlit.app` URL.

Live results are cached for 2 minutes (`@st.cache_data(ttl=120)`); reload to
refresh.

## How it works

| File | Responsibility |
|------|----------------|
| `data.py` | Providers: football-data.org adapter + seed loader; builds round-robin fixtures |
| `standings.py` | Group tables with FIFA tiebreakers; third-place ranking |
| `bracket.py` | Official R32→Final structure; third-place slot allocation (constraint solver over FIFA's eligibility sets) |
| `project.py` | Deterministic bracket projection from current standings |
| `simulate.py` | Monte-Carlo: Poisson goals, rating-weighted penalties |
| `app.py` | Streamlit UI |

### Notes & limitations

- The third-place → R32 slotting is resolved by **constraint matching** over
  FIFA's published eligibility sets rather than hardcoding the 495-row Annex C
  table. Every one of the 495 possible group combinations yields a valid,
  rules-consistent assignment; in rare ambiguous cases the specific slot may
  differ from FIFA's exact table choice.
- The strength model is intentionally simple. Drop better ratings (e.g. Elo
  or FIFA ranking points) into `seed_ratings` in `seed_data.json` for sharper
  odds.
- The seed file's groups E/F/H and results reflect real reporting as of
  2026-06-23; other groups are plausible fillers. **Live data is the source of
  truth.**
```
