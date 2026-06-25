# Hosting the always-on demo

The demo (`app/server.py`) needs two things running: **Ollama with the model**, and the
**FastAPI server**. The `Dockerfile` here bundles both into one container with the model
**baked in**, so it boots fast. Pick one host below.

> **Honest expectations:** there is no free always-on LLM hosting. A small cloud box
> costs **~$3–5/month**. Its CPU is slower than your Mac, so replies take **a few seconds**
> (vs. instant locally) — fine for a "try before you download" demo. The downloadable
> local version is the fast one.

The demo uses the **browser's** speech-to-text/text-to-speech, so the server does NOT need
Whisper/Kokoro/torch — just Python + Ollama + the 1.5B model (~2 GB RAM).

---

## Option A — Fly.io (no SSH, deploy from the repo)

```bash
# 1. install flyctl + sign in (needs a card; usage is small)
brew install flyctl
fly auth login

# 2. from the repo root, with deploy/fly.toml present:
#    edit the `app = "..."` name in deploy/fly.toml to something unique first.
fly launch --copy-config --dockerfile deploy/Dockerfile --no-deploy
fly deploy --config deploy/fly.toml
```
Your link: `https://<your-app-name>.fly.dev`. It stays on (`min_machines_running = 1`).
If it crashes on boot, bump `memory` to `"4gb"` in `deploy/fly.toml` and `fly deploy` again.

---

## Option B — a cheap VPS (most RAM per dollar, needs basic SSH)

Any ~$5/mo box with 2–4 GB RAM (Hetzner CX22 ≈ €4, DigitalOcean, Linode). After
`ssh`ing in with Docker installed:

```bash
git clone https://github.com/andrewphankt/drivethru-voice-ai && cd drivethru-voice-ai
docker build -f deploy/Dockerfile -t drivethru-demo .
docker run -d --restart always -p 80:8000 --name demo drivethru-demo
```
Now `http://<your-server-ip>` works. For **https** (needed for the mic) + a domain, put
[Caddy](https://caddyserver.com/) in front — it auto-issues a TLS cert:
```bash
# /etc/caddy/Caddyfile
your-domain.com {
    reverse_proxy localhost:8000
}
```

---

## After it's live
Drop the URL into the main `README.md` (replace the demo placeholder) so visitors can
try it before cloning.
