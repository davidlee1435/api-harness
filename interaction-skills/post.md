# POST / PUT / PATCH

Use `json_body=` for JSON payloads (sets `Content-Type: application/json` automatically). Use `data=` for raw bytes/strings (form-encoded, XML, multipart, etc.).

```python
post("https://api.example.com/things", json_body={"name": "x", "tags": ["a", "b"]})

post(
    "https://api.example.com/upload",
    data=urllib.parse.urlencode({"key": "value"}).encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
```

`put(url, **kw)` and (if you add it) PATCH are identical shape — they go through `request()`.

## Idempotency keys

Many APIs (Stripe, etc.) want an `Idempotency-Key` header so retries don't double-charge. The harness retries on 5xx by default — pass one when the call has side effects:

```python
post(url, json_body=payload, headers={"Idempotency-Key": str(uuid.uuid4())})
```

## Multipart uploads

Stdlib doesn't have a clean multipart builder. For one-offs, use `email.message`:

```python
from email.message import EmailMessage
msg = EmailMessage()
msg.add_attachment(file_bytes, maintype="application", subtype="octet-stream", filename="x.bin")
boundary = msg.get_boundary()
body = msg.as_bytes().split(b"\n\n", 1)[1]  # strip the email headers
post(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
```

If you do this more than once, add a `multipart_post()` helper to `helpers.py`.

## Don't

- Don't `json.dumps()` and pass via `data=` — use `json_body=` so the content type and encoding are right.
- Don't set `Content-Length` manually. `urllib` does it.
