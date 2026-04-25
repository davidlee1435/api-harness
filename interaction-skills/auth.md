# Auth

Three patterns cover ~90% of APIs:

## Bearer token

```python
headers = {"Authorization": f"Bearer {os.environ['TOKEN']}"}
get(url, headers=headers)
```

GitHub, OpenAI, Anthropic, Slack (user tokens), Notion, Linear.

## API key in a custom header

```python
headers = {"X-API-Key": os.environ["COINMARKETCAP_API_KEY"]}
```

CoinMarketCap (`X-CMC_PRO_API_KEY`), SendGrid, many smaller APIs. The header name is API-specific — record it in `domain-skills/<api>/`.

## API key in query params

```python
get(url, params={"api_key": os.environ["KEY"]})
```

Older APIs, some weather/finance services. Treat the URL as sensitive — don't log it.

## Storing keys

Put them in `.env` (gitignored). Never hard-code them. Never commit them. Never write them into `domain-skills/`.

```bash
# .env
GITHUB_TOKEN=ghp_...
COINMARKETCAP_API_KEY=...
```

`helpers.py` auto-loads `.env` on import.

## OAuth (3-legged)

Out of scope for the harness — needs a browser redirect. Use the API's CLI (`gh auth login` for GitHub, `slack` CLI, etc.) to get a token, then drop the token into `.env`.

For 2-legged OAuth (client credentials), it's just two HTTP calls:

```python
tok = post(
    "https://auth.example.com/oauth/token",
    data=urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ["CLIENT_ID"],
        "client_secret": os.environ["CLIENT_SECRET"],
    }).encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)["access_token"]
```

Cache it — most are valid for 1+ hours. Re-fetch on 401.

## Signed requests (AWS SigV4, etc.)

Don't reimplement. Use `boto3` (AWS), `google-auth` (GCP), the official SDK. The harness is for "thin wrapper over HTTP" APIs — when the API requires request signing, the SDK is doing real work.

## Don't

- Don't print headers in logs/errors. Strip `Authorization` before logging.
- Don't put tokens in URLs except when the API requires it.
- Don't share `.env` across machines via dotfiles. Per-machine secrets, please.
