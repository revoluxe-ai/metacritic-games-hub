# Submission report — Skytec Games AI Automation Engineer test

## Live ingestion verification (2026-11-12)

Full manual job: **20/20 games** from live Metacritic (`source: new_releases+browse`), SQLite DB `metacritic_ingest.db`, `LLM_API_KEY` unset (heuristic summaries), `YOUTUBE_ENABLED=false` for ingest speed.

| # | Title |
|---|--------|
| 1 | The Legend of Zelda: Ocarina of Time |
| 2 | Phantom Blade Zero |
| 3 | Call of Duty: Modern Warfare 4 |
| 4 | Final Fantasy Resonance |
| 5 | Nintendo Switch Sports Resort |
| 6 | Gears of War: E-Day |
| 7 | Castlevania: Belmont's Curse |
| 8 | Clive Barker's Hellraiser: Revival |
| 9 | Star Wars: Galactic Racer |
| 10 | Flea Madness |
| 11 | Scarecrow: 90s Crime Story |
| 12 | Menes: The Chainbreaker |
| 13 | Vitavania |
| 14 | Against the Horde |
| 15 | LOST IN THE DARK LABYRINTH |
| 16 | Doom Keeper |
| 17 | Ophelia's Paradise |
| 18 | Explosiovania |
| 19 | Broken Horror Anthology |
| 20 | Rolls and Dungeons |

Command: `DATABASE_URL=sqlite:////workspace/metacritic_ingest.db LLM_API_KEY= YOUTUBE_ENABLED=false python3 -m scripts.run_full_ingestion`

## Railway single-service deploy

- `RUN_SCHEDULER=true` starts **BackgroundScheduler** inside FastAPI (`app/scheduler.py`, lifespan in `app/main.py`).
- `railway.json`, `Procfile`, `scripts/railway_start.sh` — one web process + Postgres via `DATABASE_URL`; SQLite if unset.
- Docker Compose `app` service uses the same start script with `RUN_SCHEDULER=true`.

## What is implemented

1. Hourly / manual ingestion (20 games, daily New Releases + browse backfill).
2. Metacritic JSON API + per-platform scores + review samples.
3. LLM summaries with **readable heuristic fallback** (`What people like:` / `What people dislike:`).
4. Full UI + worker SSE monitor + Run now.
5. Similar games (TF-IDF), optional YouTube when `YOUTUBE_ENABLED=true`.
6. Docker, DEPLOY.md, tests, screenshots under `docs/screenshots/`.

## Limitations

- New Releases HTML yields ~9 slugs; first daily run **backfills from browse** to reach 20 (documented in README).
- YouTube step skipped when disabled or no captions.
- Docker not executed in cloud VM; compose/Railway config verified by file review + local SQLite ingest.

## Tests

`pytest` — parsing, similarity, heuristic summary format.
