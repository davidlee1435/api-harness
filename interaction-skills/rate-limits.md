# Rate limits

Most APIs publish a per-minute or per-hour quota. The 429 path in `request()` handles transient spikes; **sustained throughput** is your job.

## Detect the actual limit

Document headers vary:

- `X-RateLimit-Limit` / `X-RateLimit-Remaining` / `X-RateLimit-Reset` (GitHub, Stripe, many).
- `RateLimit-Limit` / `RateLimit-Remaining` / `RateLimit-Reset` (RFC draft, newer APIs).
- `Retry-After` only on 429 (older APIs, no proactive signal).

`request()` doesn't expose headers today. To pace proactively, drop to `urllib.request` for the call and read `r.headers.get("X-RateLimit-Remaining")` yourself, or extend `request()` to return them.

## Pace, don't react

Waiting for 429s wastes budget. If the doc says 30 req/min, pace at 30 req/min:

```python
import time

interval = 60 / 30  # 2s between calls
for thing in things:
    rows.append(get(f"{url}/{thing['id']}"))
    time.sleep(interval)
```

For burstier APIs, use a token bucket:

```python
import time
tokens, rate, last = 30.0, 30/60, time.monotonic()
def take():
    global tokens, last
    now = time.monotonic()
    tokens = min(30, tokens + (now - last) * rate)
    last = now
    if tokens < 1:
        time.sleep((1 - tokens) / rate)
        tokens = 0
    else:
        tokens -= 1
```

## Documented vs real

The published limit and the enforced limit are often different. Record what *actually* triggered 429 in `domain-skills/<api>/` — future agents shouldn't rediscover it.

## Parallelism

For independent reads, `concurrent.futures.ThreadPoolExecutor` is fine — `urllib` releases the GIL during the network wait:

```python
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(lambda u: get(u, headers=h), urls))
```

But: 8 parallel × 30 req/min limit = you'll 429 in seconds. Either pace per worker, or use a global semaphore.

## Don't

- Don't crank `retries=` up to mask a rate-limit problem. You'll just spend longer hitting 429.
- Don't share a single API key across parallel agents on the same project — most quotas are per-key.
- Don't log raw `Retry-After` values without checking — some APIs return seconds, some HTTP-date strings.
