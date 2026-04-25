"""Read, edit, extend -- this file is yours.

The agent's job: read API docs or an SDK, write the calls it needs *here*,
land the response into SQLite via `store()`, then query with `q()`.

Three layers, all editable:
  - HTTP:    request / get / post / put / delete   (urllib, stdlib only)
  - Storage: db / store / q                        (sqlite3, stdlib only)
  - Ingest:  read_docs / read_sdk                  (filesystem walkers)
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


# --- env ---

def _load_env():
    p = Path(__file__).parent / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


# --- HTTP ---

class HTTPError(Exception):
    def __init__(self, status: int, url: str, body: str):
        super().__init__(f"{status} {url}: {body[:200]}")
        self.status = status
        self.url = url
        self.body = body


def request(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    json_body: Any = None,
    data: bytes | str | None = None,
    timeout: float = 30.0,
    retries: int = 3,
    backoff: float = 0.5,
) -> dict | list | str:
    """One HTTP call with retries on 429/5xx and transient network errors.

    Returns parsed JSON when the response is JSON, else the decoded body string.
    Raises HTTPError on non-retryable 4xx, or after retries are exhausted."""
    if params:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(params, doseq=True)

    body: bytes | None = None
    h = dict(headers or {})
    if json_body is not None:
        body = json.dumps(json_body).encode()
        h.setdefault("Content-Type", "application/json")
    elif isinstance(data, str):
        body = data.encode()
    elif isinstance(data, (bytes, bytearray)):
        body = bytes(data)

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, method=method.upper(), headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace")
                ct = resp.headers.get("Content-Type", "")
                if "json" in ct or (raw.startswith(("{", "[")) and raw.endswith(("}", "]"))):
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return raw
                return raw
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace") if e.fp else ""
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                _sleep_for_retry(e.headers.get("Retry-After"), attempt, backoff)
                last_err = e
                continue
            raise HTTPError(e.code, url, raw) from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
                last_err = e
                continue
            raise
    raise last_err  # type: ignore[misc]


def _sleep_for_retry(retry_after: str | None, attempt: int, backoff: float) -> None:
    if retry_after:
        try:
            time.sleep(float(retry_after))
            return
        except ValueError:
            pass
    time.sleep(backoff * (2 ** attempt))


def get(url: str, **kw) -> Any:
    return request("GET", url, **kw)


def post(url: str, **kw) -> Any:
    return request("POST", url, **kw)


def put(url: str, **kw) -> Any:
    return request("PUT", url, **kw)


def delete(url: str, **kw) -> Any:
    return request("DELETE", url, **kw)


def paginate(
    url: str,
    *,
    next_key: str | None = None,
    next_param: str | None = None,
    items_key: str | None = None,
    max_pages: int = 100,
    **kw,
) -> Iterable[Any]:
    """Generic JSON paginator. Yields items one by one.

    next_key:   path in response to the next-page cursor/token (e.g. "meta.next").
    next_param: query param name to send the cursor on the next call.
    items_key:  path to the list of items (e.g. "data" or "results.items").
    Set both next_key and next_param for cursor pagination, or override yourself."""
    params = dict(kw.pop("params", None) or {})
    for _ in range(max_pages):
        page = get(url, params=params, **kw)
        items = _dig(page, items_key) if items_key else page
        if isinstance(items, list):
            yield from items
        else:
            yield items
        cursor = _dig(page, next_key) if next_key else None
        if not cursor or not next_param:
            return
        params[next_param] = cursor


def _dig(obj: Any, path: str | None) -> Any:
    if not path:
        return obj
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


# --- storage (SQLite) ---

_DB: sqlite3.Connection | None = None
_DB_PATH: str | None = None


def db(path: str | None = None) -> sqlite3.Connection:
    """Open (or reuse) the SQLite connection. Path resolves to:
    explicit arg > $AH_DB > ./api-harness.db. Same path returns the same conn."""
    global _DB, _DB_PATH
    if path is None:
        path = os.environ.get("AH_DB", "api-harness.db")
    if _DB is not None and _DB_PATH == path:
        return _DB
    if _DB is not None:
        _DB.close()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _DB = conn
    _DB_PATH = path
    return conn


def store(table: str, rows: Iterable[dict], *, key: str | tuple[str, ...] | None = None) -> int:
    """Insert (or upsert) rows into `table`. Creates the table from the first row's keys.

    key: column or tuple of columns to UPSERT on. Omit for plain INSERT.
    Non-scalar values (dict/list) are JSON-encoded.
    Returns the number of rows written."""
    rows = list(rows)
    if not rows:
        return 0
    cols = sorted({k for r in rows for k in r.keys()})
    conn = db()
    type_hints = {k: _sql_type(rows[0].get(k)) for k in cols}
    pk = (key,) if isinstance(key, str) else tuple(key) if key else ()
    col_defs = ", ".join(
        f'"{c}" {type_hints[c]}{" PRIMARY KEY" if pk == (c,) else ""}' for c in cols
    )
    pk_clause = f', PRIMARY KEY ({", ".join(f"\"{c}\"" for c in pk)})' if len(pk) > 1 else ""
    conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({col_defs}{pk_clause})')

    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(f'"{c}"' for c in cols)
    if pk:
        updates = ", ".join(f'"{c}"=excluded."{c}"' for c in cols if c not in pk)
        conflict = ", ".join(f'"{c}"' for c in pk)
        sql = (
            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
            f'ON CONFLICT ({conflict}) DO UPDATE SET {updates}'
        )
    else:
        sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})'

    with conn:
        conn.executemany(sql, [tuple(_encode(r.get(c)) for c in cols) for r in rows])
    return len(rows)


def q(sql: str, *params: Any) -> list[dict]:
    """Run a SELECT and return rows as dicts. Use this to inspect / verify."""
    conn = db()
    cur = conn.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def _sql_type(v: Any) -> str:
    if isinstance(v, bool):
        return "INTEGER"
    if isinstance(v, int):
        return "INTEGER"
    if isinstance(v, float):
        return "REAL"
    return "TEXT"


def _encode(v: Any) -> Any:
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    if isinstance(v, bool):
        return int(v)
    return v


# --- ingest (docs / SDK) ---

_DOC_EXTS = {".md", ".mdx", ".rst", ".txt", ".html"}
_CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".go", ".rb", ".java", ".rs", ".kt", ".swift"}
_SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", ".tox"}


def read_docs(root: str, *, exts: Iterable[str] | None = None, max_bytes: int = 2_000_000) -> dict[str, str]:
    """Walk `root` and return {relative_path: content} for doc-like files.
    Skips vendored / build directories. Truncates each file to max_bytes."""
    return _walk(root, set(exts) if exts else _DOC_EXTS, max_bytes)


def read_sdk(root: str, *, exts: Iterable[str] | None = None, max_bytes: int = 2_000_000) -> dict[str, str]:
    """Walk `root` and return {relative_path: content} for source files.
    Default extensions cover common SDK languages."""
    return _walk(root, set(exts) if exts else _CODE_EXTS, max_bytes)


def _walk(root: str, exts: set[str], max_bytes: int) -> dict[str, str]:
    base = Path(root).resolve()
    out: dict[str, str] = {}
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in exts:
            continue
        try:
            data = p.read_bytes()[:max_bytes]
            out[str(p.relative_to(base))] = data.decode("utf-8", "replace")
        except OSError:
            continue
    return out
