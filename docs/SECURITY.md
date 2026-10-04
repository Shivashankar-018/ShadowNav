# ShadowNav Security Notes — Local Prototype

## Protections currently in the app

- Flask binds to `127.0.0.1`, so the development server listens on the local
  computer by default.
- `SHADOWNAV_DEBUG` controls the Flask debugger. It defaults to `true` for local
  development; set it to `false` in `.env` to disable debug mode.
- Request bodies are limited to 16 KB. The route API only needs a few
  coordinates and a mode, so larger bodies are unnecessary.
- Responses include `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, and `Permissions-Policy` headers.
- Route coordinates, route mode, history limits, and history IDs are validated.
- `.env` is ignored by Git. Open-Meteo's current integration does not need an
  API key, and no key is placed in browser JavaScript.
- The app does not collect user names or accounts. Route history remains in the
  local SQLite file.
- Prediction-demo history stores only synthetic inputs and outputs in the same
  local database; it does not attach a location or user identity.

## Public demo configuration

Set `SHADOWNAV_PUBLIC_DEMO=true` when hosting a shared public instance. In this
mode, route and prediction history reads return an empty result, new requests
are not stored in history, and delete-history endpoints are disabled. This
prevents anonymous visitors from viewing or deleting another visitor's shared
route history. Leave the setting unset or `false` for local development. See
[`DEPLOYMENT.md`](DEPLOYMENT.md) for the Render demo setup and its limits.

## Configure debug mode

Open or create `.env` in the ShadowNav project folder and add:

```dotenv
SHADOWNAV_DEBUG=false
```

Save the file and restart Flask for the setting to take effect. For normal
student development, the default debug setting is convenient. Do not run the
debugger on a public or shared network.

## Current limitations

This is not a production deployment. It has no user authentication, rate
limiting, HTTPS configuration, or production WSGI server. It should remain a
local student prototype until those deployment requirements are addressed.
