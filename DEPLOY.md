# Deployment guide

## Docker Compose (VPS or local)

```bash
git clone <your-repo-url>
cd <repo>
cp .env.example .env
# Optional: LLM_API_KEY; for compose set RUN_SCHEDULER=true on app
docker compose up -d --build
```

- Web UI: `http://<host>:8742/`
- Worker monitor: `http://<host>:8742/worker`
- Health: `http://<host>:8742/health`

The `app` service runs **web + embedded scheduler** when `RUN_SCHEDULER=true`. The separate `worker` service is optional (legacy two-process layout).

## Railway (single service — recommended)

1. **New Project** → Deploy this repo (Dockerfile or Nixpacks; repo includes `railway.json` + `Procfile`).
2. Add **PostgreSQL** and link `DATABASE_URL` to the web service (Railway injects it automatically when linked).
3. Set variables (service → Variables):

| Variable | Value |
|----------|--------|
| `RUN_SCHEDULER` | `true` |
| `SCRAPER_ENABLED` | `true` |
| `GAMES_PER_RUN` | `20` |
| `SCHEDULER_INTERVAL_MINUTES` | `60` |
| `LLM_API_KEY` | optional |

4. Start command (default from `railway.json`): `sh scripts/railway_start.sh`  
   - Runs `init_db`, then Uvicorn on `$PORT` with APScheduler when `RUN_SCHEDULER=true`.
5. **Public domain** → Railway sets `PORT`; health check path `/health`.

**SQLite fallback:** if `DATABASE_URL` is unset, the app uses `sqlite:///./metacritic.db` (fine for demos; use Postgres in production).

```bash
curl -s https://<your-app>.up.railway.app/health
curl -X POST https://<your-app>.up.railway.app/api/worker/run-now
```

## Render

1. **Web Service** → Docker, connect repo, set `DATABASE_URL` from Render Postgres.
2. Docker CMD / start: `sh scripts/railway_start.sh`
3. Set `RUN_SCHEDULER=true` and other env vars from `.env.example`.

## Fly.io

```bash
fly launch --no-deploy
fly postgres create
fly secrets set DATABASE_URL=postgres://... RUN_SCHEDULER=true
fly deploy
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL (`postgresql://…`); omit for SQLite file |
| `PORT` | HTTP port (Railway/Render); defaults to `8742` locally |
| `RUN_SCHEDULER` | `true` = hourly APScheduler inside FastAPI process |
| `RUN_INGESTION_ON_STARTUP` | `true` = one ingest job when app boots |
| `METACRITIC_API_KEY` | Metacritic web API key (default included) |
| `LLM_*` | OpenAI-compatible LLM (optional; heuristic fallback) |
| `YOUTUBE_ENABLED` | `false` to skip YouTube step during ingest |
| `GAMES_PER_RUN` | Games per hourly/manual run (default 20) |
| `SCHEDULER_INTERVAL_MINUTES` | Scheduler interval (default 60) |
| `SCRAPER_ENABLED` | `false` = disable network scraping |
