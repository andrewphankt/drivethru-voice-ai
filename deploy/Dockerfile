# Always-on hosted demo in one container: FastAPI + Ollama + the baked-in model.
# Build context is the repo ROOT:  docker build -f deploy/Dockerfile -t drivethru-demo .
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Ollama (the local model server the demo calls)
RUN curl -fsSL https://ollama.com/install.sh | sh

# The demo server only needs FastAPI — no torch/whisper (the browser does speech)
RUN pip install --no-cache-dir fastapi "uvicorn[standard]"

WORKDIR /app
COPY . /app

# Bake the published model INTO the image so there's no slow first-request download.
# (Needs the model to be public on Ollama, which it is: andrewphankt/drivethru)
RUN ollama serve > /tmp/ollama-build.log 2>&1 & \
    sleep 6 && \
    ollama pull andrewphankt/drivethru && \
    (pkill -f "ollama serve" || true)

ENV PORT=8000
EXPOSE 8000
CMD ["bash", "deploy/start.sh"]
