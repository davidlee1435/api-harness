---
name: api-harness-install
description: Install and bootstrap api-harness into the current agent
---

# api-harness install

Use this file for first-time install, env setup, and debugging. For day-to-day API work, read `SKILL.md`. Always read `helpers.py` after cloning — that is where the functions live.

## Best everyday setup

Clone once into a durable location, then install as an editable tool so `api-harness` works from any directory:

```bash
git clone https://github.com/davidlee1435/api-harness
cd api-harness
uv tool install -e .
command -v api-harness
```

That keeps the command global while still pointing at the real repo, so when the agent edits `helpers.py` the next `api-harness` call uses the new code immediately. Prefer a stable path like `~/Developer/api-harness`, not `/tmp`.

If `uv` is unavailable, plain pip works too:

```bash
pip install -e .
```

## Make it global for the current agent

After install, register `SKILL.md` with the agent you are using:

- **Claude Code**: add an import to `~/.claude/CLAUDE.md` that points at this repo's `SKILL.md`, e.g. `@~/Developer/api-harness/SKILL.md`.
- **Codex**: add the file as a global skill at `$CODEX_HOME/skills/api-harness/SKILL.md` (often `~/.codex/skills/api-harness/SKILL.md`). A symlink is fine:

  ```bash
  mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/api-harness" \
    && ln -sf "$PWD/SKILL.md" "${CODEX_HOME:-$HOME/.codex}/skills/api-harness/SKILL.md"
  ```

That makes new sessions in other folders load the api-harness instructions automatically.

## Verify the install

```bash
api-harness -c "print(get('https://api.github.com/zen'))"
```

A pithy GitHub quote means HTTP works. Then check storage:

```bash
api-harness -c "
store('smoke', [{'id': 1, 'msg': 'hello'}], key='id')
print(q('SELECT * FROM smoke'))
"
```

If both succeed, you're set. The DB lands at `./api-harness.db` (or wherever `AH_DB` points).

## Environment

`.env` in the repo root is auto-loaded by `helpers.py` on import. Anything in there appears in `os.environ` unless already set. Copy `.env.example` to `.env` and add per-API keys as you go:

```bash
# .env
GITHUB_TOKEN=ghp_...
COINMARKETCAP_API_KEY=...
AH_DB=/Users/me/data/api-harness.db   # optional — overrides ./api-harness.db
```

Then in code:

```python
get('https://api.github.com/user', headers={'Authorization': f'Bearer {os.environ["GITHUB_TOKEN"]}'})
```

`AH_DB` is the only env var the harness itself reads. Everything else is whatever the API needs.

## Where the data lives

- Default DB path: `./api-harness.db` in whatever directory you ran `api-harness` from.
- Override globally with `AH_DB=/abs/path.db` in `.env`, or per-call with `db('/abs/path.db')`.
- The harness uses WAL mode, so you'll see `api-harness.db-wal` and `api-harness.db-shm` files alongside — that's normal, don't delete them.
- Inspect from the shell at any time: `sqlite3 api-harness.db ".tables"`.

## Debugging common failures

### `urllib.error.HTTPError: 401`
Auth header is missing or wrong. Print the header dict before the call to confirm the token actually loaded from `.env`. Common cause: the API expects `Authorization: Token X` or `X-API-Key: X`, not `Bearer X`.

### `urllib.error.HTTPError: 403`
Either the key is valid but lacks scope, or you're being WAF-blocked for missing a `User-Agent`. Add `headers={'User-Agent': 'api-harness/0.1'}`.

### `urllib.error.HTTPError: 429`
`request()` already retries with `Retry-After` honored. If you still see 429 after `retries=3`, the API's window is longer than the backoff — bump `retries=` or sleep between calls.

### `sqlite3.OperationalError: no such column`
You called `store()` with a row whose keys differ from the first batch's keys. Either drop the table (`q("DROP TABLE x")` won't work — use `db().execute("DROP TABLE x")`) and re-store, or `ALTER TABLE x ADD COLUMN ...` manually.

### `sqlite3.IntegrityError: UNIQUE constraint failed`
You passed `key=` but a later batch repeats a primary key without going through the upsert path — usually means the row dict is missing the key column. Confirm every row has the `key` field set.

### `json.JSONDecodeError` from `request()`
The server returned non-JSON despite a JSON-ish content type. `request()` falls back to returning the raw body string in this case — handle the `str` branch.

### `read_docs(path)` returns `{}`
Either the path is wrong, or every file has an extension outside the default set. Pass `exts={'.md', '.html', '.txt', ...}` explicitly. Vendored dirs (`node_modules`, `.git`, `dist`, `build`, `__pycache__`, `.venv`) are skipped — that's intentional.

### "I want a different DB per project"
Just `cd` into the project directory before running `api-harness`. The default path is relative.

### Resetting state
```bash
rm api-harness.db api-harness.db-wal api-harness.db-shm
```
Or surgical: `sqlite3 api-harness.db "DROP TABLE foo"`.

## Keeping the harness current

The repo is plain git. To update an editable install:

```bash
cd ~/Developer/api-harness
git pull --ff-only
```

The next `api-harness` call uses the new code (no daemon to restart, no cache to clear).

## Architecture

```text
agent → run.py -c "..." → helpers.py
                            ├── urllib  → external API
                            └── sqlite3 → ./api-harness.db
                                            ↑
                          other agents read here directly
                          (sqlite3 CLI, Python, any SQLite client)
```

- `run.py` is a `-c "code"` shim that pre-imports `helpers.py`.
- `helpers.py` holds every primitive: HTTP, storage, ingestion. Edit freely.
- The DB is the contract between the writing agent and any reader.

## Cold-start reminders

- Read `helpers.py` before writing anything. The functions you want already exist.
- Look in `domain-skills/<api>/` *before* reading external docs. Someone may have already mapped this API.
- Drop new findings into `domain-skills/<api>/` so the next run is faster.
- The DB path is relative by default — tell the user the absolute path the first time you write, so they can query it from anywhere.
