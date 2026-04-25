# Retries

`request()` retries automatically. You usually don't need to think about it.

## What's built in

- **Retries on**: 429, 500, 502, 503, 504, `URLError`, `TimeoutError`.
- **Honors `Retry-After`** (seconds — date format is rare and not parsed).
- **Exponential backoff** otherwise: `0.5 * 2^attempt`, so 0.5s → 1s → 2s.
- **Default `retries=3`** — four total attempts.

```python
get(url)                          # 4 attempts, 0.5s/1s/2s backoff
get(url, retries=5, backoff=1.0)  # more patient
get(url, retries=0)               # no retries — fail fast
```

## What's *not* retried

- 4xx other than 429 (400, 401, 403, 404, 422). These don't get better with retries — they need a fix.
- `HTTPError` raised after retries exhaust — the last status and body bubble up via `HTTPError(status, url, body)`.

## When to override

- **The API has a longer rate window than `retries=3` covers** (e.g. 60s reset, you exhaust backoff in ~3.5s). Bump `retries=` and `backoff=`, or sleep manually:
  ```python
  try:
      get(url, retries=0)
  except HTTPError as e:
      if e.status == 429:
          time.sleep(60)
          get(url)
  ```
- **You're processing in a batch and don't want a single bad item to kill the run.** Catch `HTTPError`, log, continue:
  ```python
  for thing in things:
      try:
          store("results", [get(f"{url}/{thing['id']}")], key="id")
      except HTTPError as e:
          store("errors", [{"id": thing["id"], "status": e.status, "body": e.body[:1000]}], key="id")
  ```

## Don't

- Don't add a manual retry loop *around* `get()` — you'll multiply the retry count.
- Don't retry POSTs with side effects without an `Idempotency-Key` (see `interaction-skills/post.md`).
- Don't catch and swallow without recording — write failures to a `errors` table so you can re-run the failed subset later.
