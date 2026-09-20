#!/bin/sh
# One uvicorn per app, ports 8001-8010. They share Redis, Kafka and one GPU, so the
# worker is what serialises the actual measurement work - these are just web processes.
cd "$(dirname "$0")"
PY=.venv/Scripts/python.exe
[ -x "$PY" ] || PY=python
port=8001
for dir in apps/[0-9][0-9]_*/; do
  name=$(basename "$dir")
  nohup "$PY" -m uvicorn app:app --app-dir "$dir" --port "$port" --log-level warning \
    > "/tmp/aal_${name}.log" 2>&1 &
  echo "  $name -> http://localhost:$port"
  port=$((port + 1))
done
