# CoinMarketCap

REST crypto market data — quotes, listings, metadata. Free tier ("Basic") is enough for most read tasks; paid tiers unlock historical data and higher rate limits.

## Base URL

- Production: `https://pro-api.coinmarketcap.com`
- Sandbox (free, fake data, useful for shape testing): `https://sandbox-api.coinmarketcap.com`

Same paths on both. Sandbox accepts any well-formed key.

## Auth

Header — **not** Bearer:

```python
headers = {"X-CMC_PRO_API_KEY": os.environ["COINMARKETCAP_API_KEY"]}
get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest", headers=headers)
```

Get a free key at <https://coinmarketcap.com/api/>. Store in `.env` as `COINMARKETCAP_API_KEY`.

## Key endpoints

| Endpoint | Returns |
|---|---|
| `/v1/cryptocurrency/listings/latest` | Top N coins by market cap, with current quote |
| `/v2/cryptocurrency/quotes/latest?symbol=BTC,ETH` | Latest quote for specific symbols |
| `/v1/cryptocurrency/map` | All coins (id, symbol, name, slug). ~10k rows. Cache this. |
| `/v2/cryptocurrency/info?symbol=BTC` | Logo, description, links — slow-changing metadata |
| `/v1/global-metrics/quotes/latest` | Total market cap, BTC dominance |

`v1` and `v2` coexist; `v2` paths return data keyed by symbol/id (a dict), `v1` returns a list. Read the response shape before storing.

## Pagination

Listings endpoints take `start=1&limit=5000` (1-indexed offset). No cursor. The free tier caps `limit` at 5000. Loop:

```python
all_rows = []
start = 1
while True:
    page = get(
        "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
        params={"start": start, "limit": 5000, "convert": "USD"},
        headers=headers,
    )["data"]
    if not page:
        break
    all_rows.extend(page)
    start += len(page)
    if len(page) < 5000:
        break
```

## Suggested table shape

```python
rows = [
    {
        "id": c["id"],
        "symbol": c["symbol"],
        "name": c["name"],
        "rank": c["cmc_rank"],
        "price_usd": c["quote"]["USD"]["price"],
        "market_cap_usd": c["quote"]["USD"]["market_cap"],
        "volume_24h_usd": c["quote"]["USD"]["volume_24h"],
        "percent_change_24h": c["quote"]["USD"]["percent_change_24h"],
        "last_updated": c["quote"]["USD"]["last_updated"],
    }
    for c in page
]
store("cmc_listings", rows, key="id")
```

For time-series, key on `(id, last_updated)` and *don't* upsert on `id` alone — you'll lose history.

## Rate limits

Free tier: **30 calls/minute, 10k credits/month**. Most endpoints cost 1 credit, but `listings/latest` with `limit=5000` costs more — check the call's "credits" cost in the response (`status.credit_count`). Pace at ~2s/call to stay under 30/min.

The 429 body looks like:

```json
{"status": {"error_code": 1008, "error_message": "You've exceeded ..."}}
```

`request()` retries automatically on 429.

## Gotchas

- `id` is **stable**, `symbol` is **not** (multiple coins can share a symbol — see `BCH`, the various wrapped tokens). Always store and join on `id`.
- `cmc_rank` can be `null` for delisted/inactive coins. Filter or coerce.
- `last_updated` is ISO-8601 UTC with a `Z` suffix. SQLite sorts these correctly as TEXT.
- `quote` keys depend on the `convert=` param. `convert=USD,EUR` gives both, but counts as 2 credits.
- Sandbox returns the *shape* but not real numbers — fine for schema design, useless for actual data.
- The free tier blocks historical endpoints (`/v2/cryptocurrency/quotes/historical`). 401/403 there means you need a paid plan, not a bad key.

## Don't

- Don't poll listings every minute. Once per 5 min covers all but HFT use cases and burns 1/6 the credits.
- Don't fetch `info` (metadata) on every run — it changes weekly at most. Store once, refresh manually.
