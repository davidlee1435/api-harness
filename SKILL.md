---
name: api-harness
description: Turn any API doc or SDK into working code that lands data in SQLite. Use when the user wants to call an API, scrape an SDK's surface, or build a queryable dataset from external services.
---

# api-harness

Read API docs or an SDK, write the calls you need, land the response in SQLite. The harness is three layers, all in `helpers.py` — read that file. For setup, env vars, or debugging, read `install.md`.

```
  ● agent: needs prices from CoinMarketCap
  │
  ● reads domain-skills/coinmarketcap/  → endpoint, auth, pagination shape
  ● writes get(...) + store(...)         → helpers.py is enough
  │
  ✓ data lands in api-harness.db
  ✓ next agent queries it with `sqlite3 api-harness.db "SELECT ..."`
```

## Usage

```bash
api-harness -c "print(get('https://api.github.com/zen'))"
```

- Invoke as `api-harness` — it's on `$PATH`. No `cd`, no `uv run`.
- Helpers are pre-imported: `get`, `post`, `put`, `delete`, `request`, `paginate`, `db`, `store`, `q`, `read_docs`, `read_sdk`.
- The default DB is `./api-harness.db` (override with `AH_DB=/path/to.db`).

## The loop

1. **Find or write a domain skill.** Look in `domain-skills/<api>/` first. If it doesn't exist, create one — even a stub README with base URL + auth saves the next agent's time.
2. **Ingest docs or SDK** if you have them locally:
   ```bash
   api-harness -c "
   docs = read_docs('/path/to/api-docs')
   for path, body in list(docs.items())[:5]:
       print(path, len(body))
   "
   ```
   `read_sdk('/path/to/sdk')` does the same for source code (`.py`, `.ts`, `.go`, ...). For docs that live online, use `get(url)` and pull the HTML/Markdown directly.
3. **Write the call.** Inline in `-c`, or add a helper to `helpers.py` if you'll call it more than twice.
4. **Land it.** `store('table', rows)` creates the table from the first row's keys and inserts. Pass `key=` for upsert.
5. **Verify.** `q("SELECT count(*) AS n FROM <table>")` from inside the harness, or `sqlite3 api-harness.db "..."` from the shell.

## Fetching the data back

This is the whole point — once data is in the DB, **anyone with filesystem access can read it**.

```bash
# from anywhere
sqlite3 api-harness.db ".tables"
sqlite3 api-harness.db ".schema issues"
sqlite3 api-harness.db "SELECT id, title FROM issues WHERE state='open' LIMIT 10"

# JSON output for piping into another tool
sqlite3 -json api-harness.db "SELECT * FROM issues LIMIT 5"

# CSV for spreadsheets
sqlite3 -header -csv api-harness.db "SELECT * FROM issues" > issues.csv
```

From inside the harness:

```bash
api-harness -c "
rows = q('SELECT id, title FROM issues WHERE state=? LIMIT 10', 'open')
for r in rows: print(r['id'], r['title'])
"
```

From any other Python script:

```python
import sqlite3
conn = sqlite3.connect('api-harness.db')
conn.row_factory = sqlite3.Row
for row in conn.execute('SELECT * FROM issues LIMIT 5'):
    print(dict(row))
```

The DB path is whatever `AH_DB` is set to, or `./api-harness.db` in the directory the harness ran from. Tell the user the absolute path of the DB after the first write so they (and other tools) know where it is.

## Tool call shape

```bash
api-harness -c "
# any python. helpers are pre-imported.
data = get('https://api.example.com/things', headers={'Authorization': f'Bearer {os.environ[\"EXAMPLE_KEY\"]}'})
store('things', data['items'], key='id')
print(q('SELECT count(*) AS n FROM things'))
"
```

For longer scripts, write a one-off file and `python` it directly — `helpers.py` is a normal module: `from helpers import get, store, q`.

## Search first

Search `domain-skills/` first for the API you're working on:

```bash
rg --files domain-skills
rg -n "coinmarketcap|coingecko" domain-skills
```

Only if you hit a generic mechanic (pagination, retries, auth flavors, bulk inserts), look in `interaction-skills/`. The available interaction skills are:

- interaction-skills/get.md — GET requests, query params, response handling
- interaction-skills/post.md — POST/PUT/PATCH bodies, content types
- interaction-skills/delete.md — DELETE, idempotency, soft vs hard delete
- interaction-skills/auth.md — bearer tokens, API keys, OAuth, signed requests
- interaction-skills/pagination.md — cursor, page-number, link-header, offset
- interaction-skills/retries.md — what's already built in, when to override
- interaction-skills/rate-limits.md — 429 handling, Retry-After, token buckets
- interaction-skills/storage.md — table design, upserts, JSON columns, indexes

## Always contribute back

If you learned something non-obvious about an API — an undocumented field, a real rate limit (vs the documented one), a payload that 400s without a hint, a working pagination cursor pattern — file it in `domain-skills/<api>/`. The next agent should not pay the same tax.

### What a domain skill should capture

The *durable* shape of the API — what the next agent on this API needs before it starts:

- Base URL(s), staging vs prod.
- Auth scheme — header name, token format, where to get one, refresh flow.
- Key endpoints and their payload shape (request + response sketch).
- Pagination style and the actual cursor field names.
- Real rate limits and what the 429 looks like.
- Field gotchas — fields that are sometimes null, IDs that look numeric but are strings, timestamps in unexpected timezones.
- Idempotency keys, dedupe rules, "this endpoint silently truncates over N items".
- A suggested table schema and primary key for `store(...)`.

### Do not write

- API keys, tokens, or any user-specific state. `domain-skills/` is shared.
- Run narration of the specific task you just did.
- Whole response payloads. A small example is fine; a 200KB blob is not.

## What actually works

- **Read docs / SDK with `read_docs(path)` / `read_sdk(path)`.** They walk a directory and return `{relpath: content}`. Skip the recursive grep — load the whole tree once and search in-process.
- **Start with `get(url)` and print.** Look at the shape before writing the schema.
- **`store('table', rows, key='id')`.** Upserts on `id`. The table is created from the first row; new columns are *not* auto-added on later writes — if the shape changes, drop the table or migrate.
- **Non-scalar values are JSON-encoded automatically.** A nested dict in a row becomes a TEXT column. Query with SQLite's `json_extract(col, '$.field')`.
- **Use `paginate(url, items_key='data', next_key='meta.next', next_param='cursor')`** for cursor APIs. For page-number APIs, it's usually clearer to write the loop yourself.
- **Tell the user the DB path** the first time you write. They'll want to query it.

## Design constraints

- `run.py` stays tiny — just `-c "code"` exec with helpers pre-imported.
- `helpers.py` is the agent's working surface. Edit it freely.
- Stdlib only by default (`urllib`, `sqlite3`, `json`). Don't pull in `httpx`/`requests` unless the user asks.
- No retries framework, no session manager, no config system. The four-arg `request()` already covers 429/5xx with backoff and `Retry-After`.
- One DB per project directory. Don't shard across files unless the user explicitly wants it.

## Gotchas (field-tested)

- `store()` creates the schema from the **first row's keys**. If later rows have new keys, those columns won't exist — either pre-pad rows, or drop and recreate.
- SQLite is fine with concurrent reads, but only one writer at a time. The harness sets `journal_mode=WAL` so concurrent readers + one writer works without locking issues.
- Booleans become `INTEGER` (0/1). SQLite has no native bool.
- Timestamps: store them as ISO-8601 TEXT or as Unix INTEGER. Don't mix.
- A `key=` upsert with `INSERT ... ON CONFLICT` requires the conflict columns to be the primary key. `store()` wires that automatically when you pass `key=`.
- `paginate()` stops when the cursor is missing or falsy — APIs that signal "done" via an empty list need a manual loop.
- `read_docs()` / `read_sdk()` skip `.git`, `node_modules`, `dist`, `build`, `__pycache__`, `.venv`. Pass `exts=` to widen.

## Interaction notes

- `interaction-skills/` holds reusable mechanics (HTTP verbs, auth, pagination, retries, storage patterns).
- `domain-skills/` holds API-specific maps and should be updated when you learn something durable about a service.
