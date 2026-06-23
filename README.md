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

## Live data

The app tries providers in order and falls back to the seed if none returns a
complete 12-group draw:

1. **API-Football (api-sports.io)** — *preferred*; has the live 2026 World Cup
   draw and results (league `1`, season `2026`). Free tier ≈ 100 requests/day.
2. **football-data.org** (`WC`) — fallback. World Cup is on its free tier, but
   the 2026 draw may not be fully published there yet.
3. **`seed_data.json`** — offline demo.

### API-Football (preferred)

1. Register at <https://www.api-football.com/> for a free key (direct
   api-sports.io access, or via RapidAPI).
2. Export it before running:

   ```bash
   export API_FOOTBALL_KEY=your_key_here
   # If using RapidAPI instead of direct:
   # export API_FOOTBALL_HOST=api-football-v1.p.rapidapi.com
   streamlit run app.py
   ```

The header caption flips to **`API-Football (live)`** once it loads. The
Matches tab's **top-scorers** leaderboard uses `/players/topscorers`. Per-match
goalscorers (who scored in a specific game) need the `/fixtures/events`
endpoint — one request per match, so it's skipped to stay within the free
daily quota; individual matches show scores only.

### football-data.org (fallback)

Grab a free token at <https://www.football-data.org/client/register> and set
`FOOTBALL_DATA_TOKEN`. Per-match goalscorers there require the paid "Deep Data"
plan. Results are cached for 2 minutes; reload to refresh.

## Deploy to Streamlit Community Cloud (free, one public URL)

1. Push this folder to a **public GitHub repo**.
2. Go to <https://share.streamlit.io> → **New app** → pick the repo and
   `app.py`.
3. Add your API key under **Advanced settings → Secrets**:

   ```toml
   API_FOOTBALL_KEY = "your_key_here"
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
