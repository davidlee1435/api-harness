# GET requests

`get(url, **kw)` is a thin wrapper over `request("GET", url, ...)`. It returns parsed JSON when the response looks like JSON, else the raw body string.

```python
get("https://api.github.com/repos/python/cpython")
get("https://api.example.com/things", params={"limit": 50, "since": "2025-01-01"})
get("https://api.example.com/me", headers={"Authorization": f"Bearer {os.environ['TOKEN']}"})
```

- `params=` is URL-encoded and appended (handles existing `?` in `url`). Lists are repeated: `params={"id": [1, 2]}` → `?id=1&id=2`.
- `headers=` is merged with sane defaults. If you set `Content-Type` it overrides.
- The return type is whichever the server gave: `dict` / `list` for JSON, `str` for everything else. Branch on `isinstance(resp, dict)` if it could be either.

## When to drop to `request()`

- You need the response headers (e.g. `Link`, `X-Total-Count`). `request()` doesn't expose them today — extend `helpers.py` to return `(body, headers)` if you need it.
- You need streaming — `request()` reads the whole body. For multi-GB responses, write a one-off using `urllib.request.urlopen` directly.

## Don't

- Don't hand-roll URL encoding (`url + "?" + "&".join(...)`). Use `params=`.
- Don't catch `HTTPError` and silently retry — `request()` already retries 429/5xx with backoff.
