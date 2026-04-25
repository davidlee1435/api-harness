# API Harness

The simplest, thinnest harness that lets an agent point at API docs (or an SDK), generate the calls on the fly, and land the response into a queryable SQLite database.

```
  ● agent: needs prices from CoinMarketCap
  │
  ● reads domain-skills/coinmarketcap/  → endpoint, auth, pagination shape
  ● writes get(...) + store(...)         → helpers.py is enough
  │
  ✓ data lands in api-harness.db
  ✓ next agent queries it with `sqlite3 api-harness.db "SELECT ..."`
```

No framework, no rails. Stdlib only. The agent edits the harness — `helpers.py` — when something is missing.

## Setup prompt

Paste into Claude Code or Codex:

```text
Set up https://github.com/davidlee1435/api-harness for me.

Read `install.md` first to install the harness. Then read `SKILL.md` for normal usage. Always read `helpers.py` because that is where the functions are. Once installed, run `api-harness -c "print(get('https://api.github.com/zen'))"` so we can confirm HTTP works, then `api-harness -c "store('smoke', [{'id': 1, 'msg': 'hello'}], key='id'); print(q('SELECT * FROM smoke'))"` so we confirm storage works. Then ask me which API I want to point it at.
```

## How simple is it?

- `install.md` — first-time install, env vars, debugging
- `SKILL.md` — day-to-day usage
- `run.py` — runs plain Python with helpers preloaded
- `helpers.py` — HTTP (`get/post/put/delete`, `paginate`), storage (`db/store/q`), ingestion (`read_docs/read_sdk`). The agent edits these.
- `domain-skills/<api>/` — per-API maps (auth, endpoints, pagination, gotchas)
- `interaction-skills/` — generic mechanics (auth flavors, pagination shapes, retries, table design)

## How agents read the data back

The DB is just a file. Anything that speaks SQLite can read it:

```bash
sqlite3 api-harness.db ".tables"
sqlite3 api-harness.db "SELECT * FROM <table> LIMIT 10"
sqlite3 -json api-harness.db "SELECT ... " | jq .
```

From inside the harness: `api-harness -c "print(q('SELECT ...'))"`.

## Contributing

PRs welcome — the best way to help is to **add a new domain skill** under [`domain-skills/`](domain-skills/) for an API you use. Each skill teaches the next agent the auth shape, the real rate limits, the field gotchas, and a sane table schema.

- **Skills are written by the harness, not by hand.** Run your task, and when the agent figures out something non-obvious, it should file the skill itself.
- Open a PR with the generated `domain-skills/<api>/` folder — small and focused is great.
- Bug fixes, helper improvements, and new interaction skills are equally welcome.
