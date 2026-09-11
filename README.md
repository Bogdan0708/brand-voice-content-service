# Brand Voice Content Service

> Status: implementation evidence; no live service claimed. This is a working
> microservices codebase with tests and CI — it is not deployed or operated
> as a production SaaS.

A small hospitality-marketing platform split into three FastAPI services,
sharing a common library, with brand-voice-driven content generation and
Instagram analytics ingestion.

## Services

- **`services/content-automation/generator`** — generates social captions
  with the Anthropic API, driven by YAML brand-voice profiles
  (`brand-voice/*.yaml`: tone, style elements, word choice, and
  per-platform limits for Instagram/Facebook/Twitter/TikTok). Requests for
  an unknown brand voice are rejected with `400` (`generator/app/main.py`).
- **`services/social-analytics/instagram`** — pulls recent media from the
  Meta Graph API and stores engagement metrics.
- **`services/api-gateway`** — routing/entry point for the above services.
- **`libs/common`** — shared auth (JWT), DTOs, SQLAlchemy models, and
  observability (structured logging + Prometheus metrics) used by all
  services.

## Brand voices

Three profiles ship under `brand-voice/`: `professional.yaml`,
`casual.yaml`, and `luxury.yaml`. Each defines a `tone`, `style_elements`,
`word_choice`, and a `platforms` map with per-platform character limits,
hashtag counts, and emoji usage. Add a new voice by dropping another YAML
file with the same shape into that directory.

## Running

```bash
docker compose -f docker-compose.production.yml up
```

This brings up the three services plus Postgres and Redis. Copy
`.env.example` to `.env` and fill in real credentials first (API keys,
JWT secret, DB/Redis passwords) — none are included in this repository.

## Tests

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

Tests cover both services' health endpoints, successful caption
generation, the unknown-brand-voice `400` path, and Instagram analytics
fixtures — all against an in-memory SQLite DB and a fake Redis client, with
no external network calls.

## CI

`.github/workflows/ci.yml` runs ruff, mypy, the test suite (against real
Postgres/Redis service containers), a Bandit security scan, a Safety
dependency check, and a TruffleHog secrets scan on every push/PR.
