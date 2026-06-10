# Insight Engine

One web-research endpoint for LLM agents. An agent sends a `type` and a `query`, and gets back clean, cited JSON. Backed by Perplexity (Search API for raw results, Sonar for synthesis).

See `plan.md` for the full design rationale.

## Quick start

```bash
# 1. Clone / cd into the project
cd insight-engine

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install
pip install -e ".[dev]"

# 4. Configure
cp .env.example .env
# Edit .env and add your INSIGHT_PERPLEXITY_API_KEY

# 5. Create an API key
python -m insight.cli create "my-agent"
# Save the key it prints — you'll need it for requests

# 6. Run
python run.py
# Server starts at http://127.0.0.1:8000
```

No Perplexity key yet? Run fully offline with the mock provider:

```bash
INSIGHT_PROVIDER=mock python run.py
```

Interactive API docs at http://127.0.0.1:8000/docs.

## Authentication

All `/insight` requests require a Bearer token. Keys are stored in a CSV file (`keys.csv` by default).

### Managing keys

```bash
# Create a key
python -m insight.cli create "my-agent"
#   Name:  my-agent
#   Key:   ink_a1b2c3d4...
#   Save this key — it won't be shown again.

# List keys (values are masked)
python -m insight.cli list

# Revoke a key
python -m insight.cli revoke "my-agent"
```

After installing with `pip install -e .`, you can also use the `insight-keys` command:

```bash
insight-keys create "my-agent"
insight-keys list
insight-keys revoke "my-agent"
```

### Using keys in requests

```bash
curl -s http://127.0.0.1:8000/insight \
  -H 'Authorization: Bearer ink_your_key_here' \
  -H 'Content-Type: application/json' \
  -d '{"type":"search","query":"python async frameworks"}'
```

Public endpoints (`/health`, `/types`, `/docs`) do not require auth.

To disable auth entirely (e.g. for local dev), set `INSIGHT_AUTH_ENABLED=false` in `.env`.

## Usage

```bash
# Raw search
curl -s http://127.0.0.1:8000/insight \
  -H 'Authorization: Bearer ink_your_key_here' \
  -H 'Content-Type: application/json' \
  -d '{"type":"search","query":"python async frameworks"}'

# Synthesized recommendation
curl -s http://127.0.0.1:8000/insight \
  -H 'Authorization: Bearer ink_your_key_here' \
  -H 'Content-Type: application/json' \
  -d '{"type":"recommend","query":"best budget over-ear headphones under $100"}'

# Health check (no auth needed)
curl http://127.0.0.1:8000/health

# Discover available types (no auth needed)
curl http://127.0.0.1:8000/types
```

## Actions (`type`)

| type | returns | backed by | paginated |
|------|---------|-----------|-----------|
| `search` | ranked web results | Search API | yes |
| `news` | recent results (last week) | Search API | yes |
| `local` | nearby places/services | Search API | yes |
| `deals` | price / where-to-buy results | Search API | no |
| `answer` | synthesized, cited answer | Sonar | no |
| `recommend` | ranked product picks | Sonar | no |
| `compare` | side-by-side + verdict | Sonar | no |
| `reviews` | sentiment / pros / cons summary | Sonar | yes |
| `alternatives` | competitors / substitutes | Sonar | no |

Raw modes use Perplexity's **Search API** (flat $5/1k requests). Synth modes use **Sonar** ($1/1M tokens + request fee). This routing is the main cost lever.

## Request fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `type` | yes | — | One of the actions above |
| `query` | yes | — | Natural-language query (1-2000 chars) |
| `safety` | no | `true` | Content filter on/off |
| `page` | no | `1` | Page number (paginated modes only) |

## Response shape

```json
{
  "type": "recommend",
  "query": "...",
  "results": [{"title": "...", "url": "...", "snippet": "...", "date": null}],
  "answer": "synthesized text (synth modes only)",
  "sources": ["https://..."],
  "page": 1,
  "has_more": false,
  "safety_applied": true
}
```

Errors are always structured:

```json
{"error": {"code": "INVALID_REQUEST", "message": "..."}}
{"error": {"code": "AUTH_REQUIRED", "message": "Missing Authorization header..."}}
{"error": {"code": "INVALID_API_KEY", "message": "The provided API key is invalid..."}}
```

Other endpoints: `GET /health`, `GET /types`.

## Tests

```bash
pytest          # runs against mock provider — no key or network needed
pytest -v       # verbose output
```

## Config (.env)

See `.env.example`. Key settings:

- `INSIGHT_PROVIDER` — `perplexity` (default) or `mock`
- `INSIGHT_PERPLEXITY_API_KEY` — your Perplexity API key
- `INSIGHT_PERPLEXITY_SYNTH_MODEL` — Sonar model tier (default: `sonar`)
- `INSIGHT_PERPLEXITY_SEARCH_CONTEXT` — `low` / `medium` / `high` (low = cheapest)
- `INSIGHT_AUTH_ENABLED` — `true` (default) or `false` to disable auth
- `INSIGHT_KEYS_FILE` — path to the CSV keystore (default: `keys.csv`)
- `INSIGHT_PAGE_SIZE` — results per page (default: 10)
- `INSIGHT_CACHE_ENABLED` / `INSIGHT_CACHE_TTL_SECONDS` — in-memory result cache
- `INSIGHT_SAFETY_BLOCKLIST` — comma-separated domains to block

## Project layout

```
src/insight/
  main.py              FastAPI app + endpoints + error handlers
  engine.py            dispatch: route -> provider -> cache -> paginate -> safety
  models.py            request/response schemas + InsightType enum
  config.py            env-based settings (pydantic-settings)
  auth.py              Bearer token auth dependency
  keystore.py          CSV-backed API key storage
  cli.py               CLI for key management (create/list/revoke)
  cache.py             optional TTL cache
  safety.py            domain blocklist + content filter (v1)
  errors.py            structured error types
  modes/handlers.py    per-mode query shaping + Sonar system prompts
  providers/
    base.py            SearchProvider interface
    perplexity.py      real adapter (Search API + Sonar)
    mock.py            offline adapter for tests/dev
keys.csv               API keys (auto-created, gitignore this)
tests/test_api.py
pyproject.toml
run.py                 dev entrypoint (uvicorn with reload)
.env.example
```

## Known limits

- **Pagination depth:** Perplexity Search API caps at 20 results, so paging is a client-side slice (~2 pages at default size).
- **Safety is v1:** domain blocklist + term filter. Better classifier is a later swap-in.
- **Scale work deferred.** The cache is the one cheap piece kept early.

## Future swap-ins

The provider is behind a small interface (`SearchProvider`), so Brave / Tavily / Exa / Firecrawl adapters can be added later without touching modes or engine logic.
