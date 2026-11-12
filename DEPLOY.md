# Deployment guide

## Docker Compose (VPS or local)

```bash
git clone <your-repo-url>
cd <repo>
cp .env.example .env
# Optional: set LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
docker compose up -d --build
```

- Web UI: `http://<host>:8742/`
- Worker monitor: `http://<host>:8742/worker`
- Health: `http://<host>:8742/health`

## Railway

1. New project → **Deploy from GitHub** (or push this repo).
2. Add **PostgreSQL** plugin; copy `DATABASE_URL` into service variables.
3. Create **two services** from the same image:
   - **Web**: start command `sh -c "python -m scripts.init_db && python -m scripts.seed --if-empty && uvicorn app.main:app --host 0.0.0.0 --port $PORT"`
   - **Worker**: start command `sh -c "python -m scripts.init_db && python -m worker.main"`
4. Set env vars from `.env.example` on both services.
5. Generate domain for the web service (port from Railway `$PORT`).

## Render

1. **New Web Service** → Docker, connect repo.
2. Add **PostgreSQL** database; set `DATABASE_URL` on the web service.
3. Docker command (override): same as Railway web command using `$PORT`.
4. **Background Worker** service: `python -m worker.main` with the same `DATABASE_URL`.

## Fly.io

```bash
fly launch --no-deploy
fly postgres create
fly secrets set DATABASE_URL=postgres://...
fly deploy
```

Run worker as a second process in `fly.toml` or a separate `worker` app with `python -m worker.main`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `METACRITIC_API_KEY` | Metacritic web API key (default included) |
| `LLM_*` | OpenAI-compatible LLM (optional) |
| `GAMES_PER_RUN` | Games per hourly/manual run (default 20) |
| `SCHEDULER_INTERVAL_MINUTES` | Worker interval (default 60) |
| `SCRAPER_ENABLED` | Set `false` to disable network scraping |

## Post-deploy check

```bash
curl -s https://<your-host>/health
curl -X POST https://<your-host>/api/worker/run-now
```
