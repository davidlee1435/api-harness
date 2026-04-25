# Pagination

Four common shapes. Pick by reading the API docs once, then encode the choice in `domain-skills/<api>/`.

## Cursor / token (use `paginate()`)

The response carries an opaque token; you echo it back as a query param.

```python
for item in paginate(
    "https://api.example.com/things",
    items_key="data",        # path to the list of items in the response
    next_key="meta.next",    # path to the cursor in the response
    next_param="cursor",     # query param name to send the cursor on
    headers=auth_headers,
):
    ...
```

`paginate()` stops when the cursor is missing/falsy.

## Page number (write the loop)

```python
page = 1
while True:
    resp = get(url, params={"page": page, "per_page": 100}, headers=auth_headers)
    if not resp:
        break
    rows.extend(resp)
    if len(resp) < 100:
        break
    page += 1
```

Don't trust a `total_pages` field — APIs lie about it. Stop on a short page or empty list.

## Offset / limit

Same shape as page number, just with `offset += limit`.

```python
offset = 0
while True:
    chunk = get(url, params={"offset": offset, "limit": 200})["items"]
    if not chunk:
        break
    rows.extend(chunk)
    offset += len(chunk)
```

## Link header (RFC 5988 — GitHub, etc.)

`request()` doesn't surface response headers today. Two options:

1. Extend `request()` to return `(body, headers)` — small change in `helpers.py`.
2. Use `urllib.request.urlopen` directly for this one call:

   ```python
   import urllib.request
   req = urllib.request.Request(url, headers=auth_headers)
   with urllib.request.urlopen(req) as r:
       link = r.headers.get("Link", "")
       data = json.loads(r.read())
   ```

   Parse `Link: <...>; rel="next"` to find the next URL.

## Don't

- Don't fetch every page into memory just to call `store()` once. Stream into the DB:
  ```python
  for batch in chunks(paginate(url, ...), 500):
      store("things", batch, key="id")
  ```
- Don't re-fetch from page 1 on retry — track the last-stored cursor (in a `_state` table or just in memory) so you resume.
- Don't assume page size is honored — APIs cap silently.
