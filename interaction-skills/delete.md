# DELETE

```python
delete("https://api.example.com/things/123")
delete(url, headers={"If-Match": etag})  # conditional delete
```

Most APIs return 204 No Content. `request()` returns the empty string in that case — don't try to `.get(...)` on it.

## Idempotency

DELETE is supposed to be idempotent — calling it twice should leave the same end state. In practice some APIs return 404 on the second call. Treat 404 as "already gone" if that's the desired outcome:

```python
try:
    delete(url)
except HTTPError as e:
    if e.status != 404:
        raise
```

## Soft vs hard delete

- **Soft** (`PATCH /things/123 {"deleted": true}` or `POST /things/123/archive`) is more common in modern APIs. Read the docs — calling DELETE on a soft-delete API may permanently remove the record.
- **Hard** is rarely reversible. Confirm with the user before deleting anything you didn't create in this session.

## Don't

- Don't loop DELETE for bulk deletes without checking for a bulk endpoint first. Most APIs have one (`POST /things/bulk_delete`).
- Don't delete and re-create as a "reset" — many APIs reuse IDs or have side effects (webhook fires, audit log entries).
