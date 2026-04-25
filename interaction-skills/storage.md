# Storage (SQLite)

`store(table, rows, key=None)` is the only write primitive. `q(sql, *params)` is the only read primitive. Both go through `db()`, which opens (or reuses) the SQLite connection.

## Table creation

`store()` creates the table from the **first row's keys**. Types are inferred from the first row's values:

| Python type            | SQL type  |
|------------------------|-----------|
| `int`, `bool`          | INTEGER   |
| `float`                | REAL      |
| anything else, `None`  | TEXT      |
| `dict`, `list`         | TEXT (json-encoded) |

If later rows have new keys, **those columns won't exist** — the insert will fail with `no such column: foo`. Two ways to handle:

1. **Pre-pad rows** to a known shape before storing:
   ```python
   keys = {"id", "name", "tags", "created_at"}
   rows = [{k: r.get(k) for k in keys} for r in rows]
   store("things", rows, key="id")
   ```
2. **Migrate when the API adds fields**:
   ```python
   db().execute('ALTER TABLE things ADD COLUMN new_field TEXT')
   ```

## Upsert

Pass `key=` to upsert on conflict:

```python
store("things", rows, key="id")              # single-column PK
store("prices", rows, key=("symbol", "ts"))  # composite PK
```

Internally: `INSERT ... ON CONFLICT(<key>) DO UPDATE SET <other_cols>=excluded.<other_cols>`. The conflict target must be the primary key — `store()` makes it so when you pass `key=`. **Don't pass `key=` to a table that already exists without a PK** — the conflict clause won't fire.

## JSON columns

Nested dicts/lists are stored as JSON text. Query with SQLite's JSON functions:

```sql
SELECT json_extract(payload, '$.user.id') AS user_id
FROM events
WHERE json_extract(payload, '$.type') = 'click';
```

Index a frequently-filtered JSON field:

```python
db().execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(json_extract(payload, '$.type'))")
```

## Indexes

`store()` doesn't create indexes beyond the PK. Add them yourself when queries get slow:

```python
db().execute("CREATE INDEX IF NOT EXISTS idx_things_created_at ON things(created_at)")
```

## Schemas across APIs

One DB per project, **multiple tables for one API is fine**. Naming convention:

- `<api>_<entity>` — `gh_issues`, `cmc_quotes`, `stripe_charges`.

Keeps tables grouped when you `.tables` and avoids collisions if two APIs both have a `users` table.

## Reading from outside the harness

```bash
sqlite3 api-harness.db ".tables"
sqlite3 api-harness.db ".schema gh_issues"
sqlite3 -json api-harness.db "SELECT * FROM gh_issues LIMIT 5"
```

Any SQLite client works — DBeaver, TablePlus, DataGrip, the VS Code SQLite extension, etc.

## Concurrency

`db()` enables WAL mode, so:

- Many readers + one writer is fine.
- Two writers is not — the second blocks. Don't run two `api-harness` writers against the same DB simultaneously. Either serialize, or shard by `AH_DB`.

## Don't

- Don't store binary blobs (images, PDFs) in TEXT columns. Save the file to disk, store the path.
- Don't store full HTML pages unless you'll query them — keep response bodies in a `_raw` table only when debugging schema issues.
- Don't `DROP TABLE` without telling the user. They may have queried it.
- Don't rely on insertion order — always include a timestamp column if order matters.
