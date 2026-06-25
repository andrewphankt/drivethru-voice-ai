#!/usr/bin/env bash
# Start Ollama, wait for it, then launch the demo server.
set -e

ollama serve > /tmp/ollama.log 2>&1 &

echo "waiting for ollama..."
until curl -s http://localhost:11434/api/tags >/dev/null 2>&1; do sleep 1; done
echo "ollama ready — starting demo on :${PORT:-8000}"

exec python3 app/server.py
