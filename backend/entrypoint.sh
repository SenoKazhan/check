#!/bin/sh
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Initializing application data..."
python -m app.core.initial_data

echo "Starting application server..."
# exec заменяет процесс оболочки процессом uvicorn (PID 1), 
# что гарантирует корректную передачу сигналов SIGTERM от Docker.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000