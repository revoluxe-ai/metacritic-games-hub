#!/bin/sh
set -e
python -m scripts.init_db
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8742}"
