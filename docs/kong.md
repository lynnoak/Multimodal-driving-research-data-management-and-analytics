# Kong Gateway

The DB-less configuration is `kong/kong.template.yml`. The entrypoint validates the server key and minute limit, then renders a restricted temporary configuration inside the container. No real key is baked into images or templates.

Public Demo proxy: **http://localhost:18000**. Requests preserve paths and route internally to `fastapi:8000`. `/api/v1/*` requires the `X-API-Key` header. Query/body API keys are disabled; credentials are removed before forwarding. `/health`, `/docs`, `/redoc` and `/openapi.json` are public. Swagger's Authorize control attaches the required header.

Missing or invalid keys return 401. The default limit is 60 requests per minute per consumer, configured by `DEMO_RATE_LIMIT_PER_MINUTE` in ignored `.env.demo`. Exceeding it returns 429 with retry headers. The local policy keeps counters in memory and resets them when Kong restarts. All requests sharing the Demo consumer share its bucket. Kong's Admin API is disabled and has no published port.

After changing Demo credentials or limits, run the documented Compose command again. The real gateway tests intentionally exhaust the development bucket. To reset only this synthetic Demo's counters:

```powershell
docker compose --env-file .env.demo -f compose.demo.yaml -p driving-simulator-demo restart kong
```

Never print the complete rendered configuration or full Compose configuration with environment values: they contain credentials. This gateway is a local demonstration, not a complete external-deployment security design.
