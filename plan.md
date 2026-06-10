# Insight Engine — Plan & Ideation

> A single backend service that browses the web and returns useful, structured insight: search results, product recommendations, review summaries, and comparisons. One flexible endpoint, several "modes."

Status: **Ideation / planning.** Nothing is built yet. This document captures the thinking so we can lock decisions before writing code.

---

## 1. Vision

Build one service ("Insight Engine") that takes a natural-language query plus a *mode*, goes out to the web, reads what it finds, and returns a clean, structured result. The point of difference from a raw search API is that we **read and synthesize** the pages, not just hand back links.

The same plumbing (fetch → parse → clean → synthesize) powers every mode. The mode mostly changes the *prompt/shape* of the output and *which sources* we prioritize.

### Who calls this: **LLM agents.**

This is **a tool / skill for other agents**, not a human-facing UI. That decision drives the whole design:

- **Machine-readable I/O.** Deterministic, predictable JSON. No prose-y wrapping, no UI concerns.
- **Stable, self-describing schema.** Field names and result shapes stay consistent across calls so an agent can rely on them. Good descriptions so the tool is easy to register in an agent's tool list.
- **Structured errors.** Failures come back as parseable JSON (`error.code`, `error.message`), never as free text an agent has to guess at.
- **Citations always.** Agents need provenance to ground their own outputs, so every result carries source URLs.
- **Future-friendly to tool/skill packaging.** Should be trivial to expose as an MCP server or as an OpenAI/Anthropic tool definition later (see §10).

---

## 2. Search modes (endpoint purposes)

Each mode is a different "shape" of answer on top of the same fetch+parse core. Pagination only makes sense where the result set is genuinely large and the user might want to dig deeper.

| Mode | What it does | Output shape | Pagination? |
|------|--------------|--------------|-------------|
| `search` | General keyword/NL web search | Ranked results: title, URL, snippet, source | **Yes** (cursor/offset) |
| `answer` | NL question → synthesized answer w/ citations | Single answer + source list | No |
| `recommend` | "best X for Y" → curated product picks | Top-N picks: name, why, price, specs, link | Light ("load more", capped) |
| `compare` | 2+ named items → side-by-side | Fixed comparison table + verdict | No (fixed set) |
| `reviews` | One product/place/service → aggregated reviews | Sentiment summary, pros/cons, rating spread, quotes\* | **Yes** (more reviews) |
| `alternatives` | "things like X" → competitors/substitutes | List of alternatives w/ 1-line diff | Light, capped |
| `deals` / `price` | Lowest price across retailers | Price-by-retailer list, sorted | Light, capped |
| `local` | Places/services near a location | Ranked nearby results + map data | **Yes** |
| `news` | Recent articles on a topic | Time-sorted articles, freshness-filtered | **Yes** |

\* Review *quotes* must be short paraphrase/snippets with attribution, not reproduced verbatim blocks — keep us clear of copyright issues.

**Pagination rule of thumb:** big, open-ended result sets (`search`, `reviews`, `local`, `news`) get real pagination. Curated/synthesized modes (`answer`, `compare`, `recommend`, `alternatives`, `deals`) are capped — a "top N" with an optional single "load more," because page 7 of recommendations is noise.

**Routing.** A thin intent-classification layer can auto-pick a mode when the caller doesn't specify one (e.g. "best running shoes under $120" → `recommend`; "iPhone 17 vs Pixel 10" → `compare`). The caller can always override.

---

## 3. The endpoint (API contract)

One endpoint. An agent sends a `type` (the action) and a `query`, plus an optional safety flag and pagination cursor.

**Request** — `POST /insight`

```json
{
  "type": "recommend",          // one of the modes in §2
  "query": "best running shoes under $120 for flat feet",
  "safety": true,               // SafeSearch-style filter; true = on (default), false = off
  "page": 1                     // optional; only used by paginated modes
}
```

- `type` *(required)* — `search | answer | recommend | compare | reviews | alternatives | deals | local | news`
- `query` *(required)* — the question / search string in natural language
- `safety` *(optional, default `true`)* — content filter on/off, per request (§7)
- `page` *(optional)* — only meaningful for paginated modes; ignored elsewhere

**Response**

```json
{
  "type": "recommend",
  "query": "...",
  "results": [ { "title": "...", "summary": "...", "url": "...", "data": { } } ],
  "answer": "optional synthesized text for answer/compare/recommend modes",
  "sources": [ "https://..." ],
  "page": 1,
  "has_more": false,
  "safety_applied": true
}
```

**Errors** — always structured, never free text:

```json
{ "error": { "code": "INVALID_TYPE", "message": "Unknown type 'reccomend'." } }
```

A single endpoint with a `type` switch keeps the agent-facing tool definition tiny (two required fields) while letting us add modes without changing the contract.

---

## 4. How search actually works (architecture)

```
query + mode
     │
     ▼
[1] Intent / routing  ──► pick mode, rewrite query, extract entities (product names, location, constraints)
     │
     ▼
[2] Source selection  ──► choose providers for this mode (web index, product API, reviews, news…)
     │
     ▼
[3] Retrieval         ──► search API call(s)  →  candidate URLs + snippets
     │
     ▼
[4] Fetch + parse     ──► pull full page content, strip nav/ads/boilerplate, get clean text
     │
     ▼
[5] Rank / filter     ──► relevance + quality + (safety filter, §8) + dedupe
     │
     ▼
[6] Synthesize        ──► LLM shapes output per mode, with citations
     │
     ▼
[7] Cache + return    ──► store result by (query, mode, page); return structured JSON
```

The interesting design choice: **search-first vs. content-first.** Some providers return just links/snippets; others return cleaned full-page content ready for an LLM. We'll likely mix — a fast search API for discovery, plus a content/extraction step for the modes that need the actual page text (`answer`, `reviews`, `compare`).

---

## 5. Provider: Perplexity (locked for v1)

**Decision: Perplexity only, no fallback for now** — one provider keeps the build simple and the bill predictable. Other providers (Brave, Tavily, Exa, Firecrawl) stay documented below as future swap-ins, since the engine talks to providers through a small adapter interface (§10) — but we are not wiring them now.

### Two Perplexity products, used for different modes

Perplexity actually exposes two relevant surfaces, priced very differently. Using the right one per mode is the main cost lever:

| Product | What it returns | Price | Use for |
|---------|-----------------|-------|---------|
| **Search API** | Raw web results (no LLM synthesis) | **$5 / 1,000 requests, flat — no token charge** (~$0.005/call) | `search`, `news`, `local`, `deals` |
| **Sonar API** (`sonar` base model) | Search **+** synthesized, cited answer | **$1 / 1M tokens** in & out, **plus** a per-request fee that scales with search context: **$5/1k (Low) → $12/1k (High)** | `answer`, `recommend`, `compare`, `reviews`, `alternatives` |

So the cheapest design isn't "everything through Sonar" — it's: **raw modes hit the flat $5/1k Search API; only the modes that genuinely need a written answer pay for Sonar**, and those run at `search_context_size: low` to keep the request fee at the bottom of the range.

```
# .env / config
SEARCH_PROVIDER=perplexity
PERPLEXITY_API_KEY=...

PERPLEXITY_SEARCH_ENDPOINT=search   # raw results for search/news/local/deals
PERPLEXITY_SYNTH_MODEL=sonar        # cheapest Sonar tier ($1/1M) for synthesis modes
PERPLEXITY_SEARCH_CONTEXT=low       # keeps the per-request fee minimal
```

### Keeping spend down (since budget is tight right now)

- Route by mode per the table above — don't pay Sonar's token+request fee for queries that only need links.
- Pin `search_context_size=low`; bump per-mode only if quality demands it.
- The optional result cache (§7) means repeated queries cost $0.
- No fallback provider, no embeddings, no extra LLM account — Sonar can also do the synthesis, so there's only one bill to watch.
- Rough order of magnitude: a raw search ≈ half a cent; a synthesized answer ≈ a fraction of a cent in tokens + ~half a cent request fee. Hundreds of calls = single-digit dollars.

### Future swap-ins (not built now)

- **LLM-native search**: Tavily, Exa, Linkup, Parallel.
- **Independent SERP / index APIs**: Brave Search API (own 30B+ page index), Google Programmable Search, SerpAPI, Serper.
- **Crawl + extract (URL → clean markdown)**: Firecrawl, Jina Reader, ScrapeGraphAI.
- **Product data**: retailer APIs (Amazon PA-API, eBay, Best Buy) for `deals`/`price`.
- Note: Microsoft's **Bing Search API was retired** — not an option.

---

## 6. Parsing the online text

For modes that read full pages (not just snippets):

1. **Fetch** the URL (or let an extraction provider do it — Firecrawl/Jina handle JS-rendered SPAs, infinite scroll, cookie banners).
2. **Extract main content** — readability-style extraction (e.g. trafilatura / readability / newspaper-type libs, or a provider that returns clean markdown). Goal: drop nav, ads, footers, comment sludge.
3. **Normalize** to clean markdown/plain text.
4. **Chunk** for the synthesis step; optionally **embed** for semantic ranking when we have many candidate passages.
5. **Hand to the LLM** with the mode-specific prompt to produce the structured output + citations.

The "self-hosted extraction (cheap, more glue code) vs. managed extraction provider (turnkey, costs more)" trade-off is a real fork. Prototype both on a handful of messy real-world pages (a product page, a review page, an article) and compare output quality before deciding.

---

## 7. Scale & rate limits — *deferred*

**Out of scope for now.** Not building queueing, backoff, or anti-throttling work in the early phases. We'll just call the provider directly and let its limits be what they are while prototyping.

Parking the one idea worth keeping cheaply: a simple result **cache** keyed by `(type, query, page)` is low effort and helps both latency and cost, so we may add it early even though the broader scale work waits. Everything else here is revisited later if real volume shows up.

---

## 8. Safety toggle

The toggle itself is **part of the request now** — the `safety` boolean in §3 (default `true`). What's deferred is the *quality* of the filtering behind it, not the switch.

- **Wire it in from the start.** The `safety` flag flows through `[5] Rank/filter` and is echoed back as `safety_applied` so the calling agent knows what it got.
- **`safety: true`** (default) — SafeSearch-style screening of explicit/graphic/harmful results, plus optional low-quality/spam source dropping.
- **`safety: false`** — unfiltered results for legitimate research; still bounded by what's legal and by provider terms. Logged so the toggle isn't silent.
- **Deferred:** the actual classifier sophistication. v1 can lean on the provider's own SafeSearch parameter (most search APIs expose one) and a simple domain blocklist; a better classifier is a later swap-in behind the same hook.

---

## 9. Proposed project structure

```
insight-engine/
├── plan.md                  # this file
├── README.md
├── pyproject.toml           # (stack — see §10)
├── .env.example             # SEARCH_PROVIDER, API keys (see §5)
├── src/
│   ├── api/                 # the /insight endpoint, request/response schemas
│   ├── router/              # type → mode dispatch (+ optional intent inference)
│   ├── providers/           # provider adapters: perplexity, brave, tavily… (swappable)
│   ├── parse/               # fetch + content extraction + cleaning
│   ├── modes/               # per-mode logic & output shaping (search, compare, …)
│   ├── synth/               # LLM synthesis + citation handling
│   ├── safety/              # safety-flag filter (provider SafeSearch + blocklist for v1)
│   ├── cache/               # optional result cache (§7)
│   └── core/                # config, models, shared types
└── tests/
```

---

## 10. Tech stack (proposed, open to change)

- **Backend:** Python + FastAPI — clean async, great for an API service, easy provider integrations. (Node/Express is a fine alternative if preferred.)
- **Provider adapter:** a small `SearchProvider` interface (`search()`, `synth()`); for v1 a single **Perplexity** adapter (Search API for raw modes, Sonar for synthesis). Interface stays so other vendors can drop in later, but only Perplexity is wired now.
- **Synthesis LLM:** Perplexity **Sonar** (base tier) — keeps search + synthesis on one provider and one bill.
- **Cache:** optional, in-memory / SQLite for the prototype (§7).
- **Agent packaging (later):** because the contract is one tiny endpoint, wrapping it as an **MCP server** or an OpenAI/Anthropic **tool definition** is a thin layer on top — the tool schema is basically `{type, query, safety}`.

---

## 11. Phased roadmap

1. **Phase 0 — Decide.** Settle the few open questions in §12 (mainly auth + v1 modes). Provider is already locked to Perplexity.
2. **Phase 1 — Core path.** The `/insight` endpoint with `type` dispatch; `search` mode end-to-end via Perplexity's Search API; structured JSON out; `safety` flag wired through (provider SafeSearch + blocklist).
3. **Phase 2 — More modes.** Add `answer`, `recommend`, `compare`, `reviews`. Add fetch+parse for content-hungry modes.
4. **Phase 3 — Remaining modes & pagination.** `alternatives`, `deals`, `local`, `news`; pagination where it applies.
5. **Phase 4 — Agent packaging.** Wrap as an MCP server / tool definition so agents can register it directly.
6. **Later (deferred).** Better safety classifier; caching/scale work (§7) if volume shows up.

---

## 12. Open questions to settle before building

- **Auth for callers.** Since agents call this, do we want a simple API key on `/insight`, or is it internal/unauthenticated for now?
- **Content extraction.** For `reviews`/`compare`, lean on Sonar's synthesized output, or add our own fetch+parse step for richer detail?
- **Budget ceiling.** Any monthly cap to design around (e.g. hard-stop or warn at $X)?
- **v1 modes.** Which of the nine are must-have for the first build vs. later?

---

### Decisions locked so far
- **Caller = LLM agents.** This is a tool/skill, not a UI. Machine-readable JSON, stable schema, structured errors, always-cited.
- **One endpoint** (`/insight`) with `type` + `query` (+ optional `safety`, `page`).
- **Provider = Perplexity only** for v1, no fallback. **Search API** ($5/1k, flat) for raw modes; **Sonar** base ($1/1M tokens + low search-context fee) for synthesis modes. Chosen to keep spend low.
- **`safety` is a per-request flag** (default on); classifier quality deferred.
- **Rate-limit / scale work is deferred.**
