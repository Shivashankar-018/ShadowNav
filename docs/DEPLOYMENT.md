# Public Demo Deployment (Render)

This guide deploys ShadowNav as a publicly reachable student demonstration. It uses Render's free web-service plan by default and the settings in the repository's `render.yaml`.

## What the public demo does

- Serves the Flask application with Gunicorn on Render's assigned port.
- Builds the synthetic training data, model artifact, and ML metrics during deployment. These generated build files do not need to be committed.
- Turns Flask debug mode off.
- Enables `SHADOWNAV_PUBLIC_DEMO`, which disables shared route and prediction history. Route endpoint coordinates should not be visible to other visitors.
- Checks `/api/status` as its health endpoint.

Local development keeps the existing history behavior because `SHADOWNAV_PUBLIC_DEMO` defaults to `false`.

## Before deployment

1. Review the app locally, including route calculation and the new public-demo history message.
2. Make sure `.env`, `.venv`, SQLite databases, trained `.joblib` files, generated training CSVs, and cached OSM network files are not staged. The repository `.gitignore` excludes these.
3. Create a **private** GitHub repository for the source. The deployed website can be public while the code repository remains private.
4. Commit and push the project to GitHub. PowerShell commands from the ShadowNav folder:

```powershell
git status --short
git add .
git status --short
git commit -m "Prepare ShadowNav public demo"
git remote add origin https://github.com/YOUR-GITHUB-USERNAME/ShadowNav.git
git push -u origin main
```

Replace `YOUR-GITHUB-USERNAME` with your GitHub username. Before committing, inspect `git status --short` and confirm `.env`, `.venv`, `data/shadownav.sqlite3`, `data/processed/`, `models/*.joblib`, and `data/sample/synthetic_heat_training.csv` are absent. If `origin` already exists, use `git remote set-url origin ...` instead of `git remote add origin ...`.

## Create the public service

1. Sign in to Render and connect the GitHub account that can access the private repository.
2. Choose **New + → Blueprint** and select the ShadowNav repository.
3. Render reads the root `render.yaml`. Confirm the service name is available and the plan is `free`, then apply the Blueprint.
4. Wait for the first build and deploy. The build installs dependencies and generates the ML teaching artifacts. Do not commit the generated model or the synthetic dataset.
5. When the service is live, copy its `onrender.com` address. The public page is the root URL, for example `https://shadownav-web-demo.onrender.com/`.
6. Test the root page and `https://YOUR-SERVICE.onrender.com/api/status`. Then select two points within the study map and calculate a route.
7. Share the root link or create a QR code from it. A custom domain is optional.

## Give it a branded address

The included Render service name is `shadownav-web-demo`, so after a
successful deployment its default address should be similar to
`https://shadownav-web-demo.onrender.com/`. The exact link is shown in the
Render dashboard after deployment. That full URL can be typed or shared in any
modern browser; it is not live until the service is deployed.

To use a shorter brand address such as `shadownav.in` or `shadownav.com`:

1. Check whether your chosen domain is available with a domain registrar and
   register it if you choose to use it. Domain registration usually has a
   recurring fee; the exact price and availability depend on the registrar and
   domain ending. This project has not checked or reserved any domain name.
2. In Render, open the deployed service's **Settings → Custom Domains** and
   add the exact domain you registered.
3. At the domain registrar, enter the DNS records Render displays for that
   domain, then return to Render and verify it.
4. Wait for DNS verification and TLS setup. Render documents automatic
   certificates and HTTPS redirects for custom domains [1].

Typing only `SHADOWNAV` with no domain ending is not a dependable public web
address. Browsers commonly treat a bare word as a search. Use the complete
`onrender.com` address or register a full custom domain such as
`shadownav.in`.

Render's Flask guide uses `pip install -r requirements.txt` and Gunicorn to run Flask in production [1]. The included Blueprint declares those settings and a health-check path [2].

## Verify after deployment

Check these in order:

1. `/api/status` responds with JSON and `"ok": true`.
2. The home page loads and Leaflet tiles appear with OpenStreetMap attribution.
3. Weather and the heat grid load; the heat layer's proxy disclaimer remains visible.
4. The road layer finishes loading. Its first request can take a few minutes because the OSM graph cache is generated on the service at runtime.
5. Set a source and destination inside the map bounds, then calculate a route and compare the three modes.
6. The route result appears and the history panels state that shared history is disabled.
7. Refresh the public link from a second browser/device to confirm it is reachable without a login.

## Free-plan limits and reliability

This is appropriate for a shareable classroom demo, not a guaranteed always-on service. Render currently spins down a free web service after 15 minutes without traffic; the next visitor may wait about a minute for it to start. Free web services also have an ephemeral filesystem, so the OSM graph cache and local files can disappear after sleep, restart, or redeploy. The route graph may then need to be downloaded again. Free service memory/CPU and external OpenStreetMap/Overpass/ weather availability can also limit response time [3].

The public setting intentionally disables shared history to avoid revealing one visitor's source/destination coordinates or demo inputs to everyone else. Local history remains enabled when you run the app on your computer. Persistent multi-user history requires a private per-user design and a managed database; do not turn on the current global history endpoints for a public audience.

For a continuously available deployment, choose an always-on plan with enough memory for the GIS/ML dependencies and set up persistent storage or a managed database. That may have a cost. Check the provider's current pricing and limits before upgrading. No hosting platform can guarantee that independent weather, map-tile, and Overpass services will always respond, so the prototype cannot promise perfect availability or route/heat accuracy.

## Troubleshooting

- **Build fails installing packages:** open Render's deploy logs and share the first package error. Confirm the service runtime is Python and `requirements.txt` is at the repository root.
- **`gunicorn: command not found`:** verify that the latest commit includes `gunicorn` in `requirements.txt`, then redeploy.
- **Health check fails:** verify the start command is `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 240 app:app` and `/api/status` is available.
- **ML metrics/model endpoint unavailable:** the build log must show all three ML commands completing after dependency installation.
- **Blank map tiles:** check the internet connection, browser console, Leaflet CDN availability, and tile-service availability. Keep OpenStreetMap attribution visible.
- **Weather error:** retry later; Open-Meteo is an external dependency. The app should show an error rather than claim a stale street measurement.
- **Walking network or route error:** retry later and check service logs. Overpass is external and may be temporarily unavailable; the first successful graph load can be slow.
- **The site sleeps:** this is expected on Render's free tier after inactivity. Open the link and allow its cold start to finish.
- **Out-of-memory or restart during startup:** the free plan may not have enough memory for this geospatial stack. Use a larger plan or a provider with suitable memory; verify the cost first.

## References

1. Render. [Custom Domains](https://render.com/docs/custom-domains) and [Deploy a Flask App](https://render.com/docs/deploy-flask).
2. Render. [Blueprint YAML Reference](https://render.com/docs/blueprint-spec).
3. Render. [Deploy for Free](https://render.com/docs/free) and [Persistent Disks](https://render.com/docs/disks).

Provider plan details change. Recheck the linked official documentation when deploying.
