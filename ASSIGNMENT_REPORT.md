# Submission report — Skytec Games AI Automation Engineer test

## What is implemented

1. **Ingestion service** — `worker` + manual `POST /api/worker/run-now`, default every 60 minutes, 20 games per run.
2. **Daily logic** — first run: New Releases HTML slugs; later runs: finder API `sortBy=-releaseDate` with increasing offset; dedup via `processed_slugs_today`.
3. **Fields** — title, cover, platforms (Metascore + user score each), developer, description, trailer/video URL, Metacritic link, genres.
4. **LLM** — OpenAI-compatible env config; heuristic fallback when no key.
5. **UI** — list, detail, platform filter, title search, rating sort, similar games (TF-IDF).
6. **Worker monitor** — SSE `/api/worker/events`, Run now button (required).
7. **Bonus YouTube** — search + subtitle transcript + short conclusion (when captions exist).
8. **Docker** — `Dockerfile`, `docker-compose.yml`, `.env.example`, `DEPLOY.md`.
9. **Tests** — `pytest` on HTML/JSON fixtures; `scripts/verify_scraper.py` for live API smoke test.
10. **Seed** — `scripts/sample_games.json` for offline UI demo.

## What is not / limitations

- **Docker** was not executed in the Cursor cloud VM (`docker` CLI missing); compose file is standard and intended for your machine/VPS.
- **YouTube** step depends on public search HTML and caption availability; may be empty for very new/obscure titles.
- **LLM quality** without API key is heuristic-only (by design).
- **Per-platform user scores** use Metacritic stats API per platform slug (extra HTTP calls per platform).
- **Public live URL** must be provisioned by you via DEPLOY.md (Render/Railway/etc.); repo is deploy-ready.

## Verification performed (2026-11-12)

```text
pytest: 4 passed
python -m scripts.verify_scraper:
  browse slugs + new release slugs + enrich OK
python -c enrich_game('hades-ii'): OK, Supergiant Games, 5 platforms
```

## How to submit

1. Push repo; share Git URL.
2. Deploy with `docker compose up` or cloud steps in DEPLOY.md; share HTTPS URL.
3. Attach Cursor agent transcript JSONL as chat history.
