# ShadowNav — System Design and Technology Stack (Step 2)

This document freezes the design for the prototype. It is a student project, not a city-scale production system.

## 1. Project overview

ShadowNav is a web application that estimates **hyper-local heat risk** on a walking map and suggests a **cooler walking route** as well as a shortest route.

City-wide weather (for example “Bengaluru is 34°C”) is not enough for walking. Streets with asphalt, little shade, and dense buildings can feel hotter than parks a few hundred metres away. ShadowNav combines:

- public weather data
- map/road geometry from OpenStreetMap
- a machine-learning heat estimator (prototype)
- a heat-aware route cost on the walking graph

**Prototype city area:** a **small bounding box** (a neighbourhood), not an entire metro. This keeps OSM downloads and routing fast on a laptop.

## 2. Problem statement

Ordinary navigation apps minimise distance or time. They do not estimate heat exposure along walking paths. During heat events this can send pedestrians through hotter streets when a slightly longer shaded or greener path may reduce heat load.

Academic and municipal work on urban heat islands (UHI) exists, but most public tools do not turn hyper-local heat estimates into a **walkable cool-route** for a student-demo web app.

## 3. Proposed solution

1. Load a walking road network for a small area.
2. Attach weather + spatial proxy features to grid cells or road segments.
3. Predict a heat intensity score per segment (temperature-like value or heat index).
4. Convert predictions to transparent risk bands (Low / Moderate / High / Very High).
5. Show the layer on an interactive map.
6. For a user source and destination, compute:
   - shortest walking route
   - cooler route (higher weight on heat)
   - balanced route
7. Store recent predictions and routes in SQLite for the dashboard.

**Honesty rule:** if true street-level temperature sensors are unavailable, the ML model is trained on a **labelled prototype/simulation dataset**. That dataset must never be presented as measured street temperatures.

## 4. Objectives

- Collect weather and simple environmental features.
- Estimate heat per small geographic unit (grid / road segment).
- Detect hotter segments relative to the local area.
- Display heat and routes on a map.
- Offer heat-aware walking alternatives, not distance-only routing.
- Show distance, time, heat metrics, and weather.
- Store demo history.
- Provide a viva-ready dashboard.

## 5. Scope

**In scope (this project)**

- Local Windows development
- One neighbourhood-scale OSM walking graph
- Open-Meteo weather (no paid API)
- Prototype heat model + risk categories
- Flask web UI + Leaflet map
- SQLite history
- Shortest / cooler / balanced modes

**Out of scope (unless added later)**

- City-wide production routing
- Medical heat-safety advice
- Real-time IoT sensor network (optional extension only)
- Driving / transit routing
- Paid map platforms (Google Maps Directions)

## 6. Functional requirements

| ID | Requirement |
|----|-------------|
| FR1 | User opens a homepage with map and navigation |
| FR2 | System fetches current weather for the study area |
| FR3 | System estimates heat per grid/segment |
| FR4 | Map shows heat overlay, legend, source, destination, routes |
| FR5 | User sets source and destination (click or search) |
| FR6 | System generates walking routes |
| FR7 | System reports distance, time, average/max heat, exposure score |
| FR8 | User selects Shortest / Cooler / Balanced |
| FR9 | System stores recent runs in SQLite |
| FR10 | APIs: status, weather, predict, heatmap, route, history |
| FR11 | Health/status endpoint for demo |

## 7. Non-functional requirements

| ID | Requirement |
|----|-------------|
| NFR1 | Runs on a student Windows laptop |
| NFR2 | Route for a small graph should return in a few seconds |
| NFR3 | No secrets in frontend JavaScript |
| NFR4 | Clear errors if weather API is down |
| NFR5 | OSM tile attribution always visible |
| NFR6 | Modular folders so each part can be tested |
| NFR7 | SQLite file local; no unnecessary personal data |

## 8. System architecture

```
Browser (HTML/CSS/JS + Leaflet)
        |  HTTP (JSON + HTML)
Flask app (app.py)
        |-- services/weather_service.py  --> Open-Meteo (internet)
        |-- ml/predict.py + models/*.joblib
        |-- gis/ (grid, OSM cache)
        |-- routing/ (NetworkX costs)
        |-- database/ (SQLite)
```

**Communication**

- Browser never calls Open-Meteo with a secret (Open-Meteo needs none; still all weather goes through Flask so we can cache and validate).
- Flask calls weather service → normalised dict.
- Predict module reads features + trained model → heat values.
- GIS module maps lat/lon to nodes/edges.
- Routing module sets edge weights from distance + heat → paths.
- Database module writes weather, predictions, routes for history.

## 9. Data flow

1. Page load → `GET /api/status` and `GET /api/weather`.
2. `GET /api/heatmap` → predictions for visible grid/edges → Leaflet heat layer.
3. User picks A and B → `POST /api/route` with mode.
4. Flask: nearest graph nodes → candidate paths → metrics → GeoJSON.
5. Flask inserts the route result (and all candidates for a comparison) into
   local SQLite history.
6. Browser draws polylines, fills the results panel, and refreshes recent history.

## 10. Module structure

| Path | Role |
|------|------|
| `app.py` | Flask routes (later) |
| `config.py` | Paths, city bbox, cost weights α, β, γ |
| `services/` | Weather HTTP client |
| `gis/` | OSM graph load/cache, grid |
| `ml/` | preprocess, train, evaluate, predict |
| `routing/` | cost function, modes |
| `database/` | SQLite schema and helpers |
| `models/` | saved `.joblib` |
| `data/` | raw / processed / sample |
| `templates/` | HTML |
| `static/` | CSS/JS/images |
| `tests/` | pytest |
| `docs/` | design notes |

## 11–13. Technology stack, software, hardware

See the frozen stack table in the chat (Step 2). Hardware: Windows laptop, 8 GB RAM preferred, internet for OSM + weather.

## 14. APIs / services

| Service | Use | Key? |
|---------|-----|------|
| Open-Meteo Forecast API | Weather | No |
| OpenStreetMap / Nominatim (optional, rate-limited) | Geocoding | No |
| OSM via OSMnx | Walking network | No |
| Leaflet OSM tiles | Base map | No (attribution required) |

## 15. Database (SQLite)

Implemented tables: `route_history` stores grouped route searches and metrics;
`prediction_history` stores only synthetic demo inputs and outputs. Both are
kept in `data/shadownav.sqlite3`, which is excluded from Git. The prototype does
not store user accounts, names, or prediction locations.

## 16. AI/ML pipeline

The current training demonstration uses a **synthetic-only** dataset and compares
Linear Regression, Random Forest, and Histogram Gradient Boosting. It selects a
model using validation MAE, then reports MAE, RMSE, and R² on a held-out test
split. These metrics measure fit to the invented simulation formula only; they
are not evidence of real-world heat accuracy. A separate `/api/predict` endpoint
and homepage demo panel show the trained model using synthetic example inputs;
`/api/ml/metrics` displays the saved validation and test reports.
The existing map heat layer and route costs remain separate, clearly labelled
proxies. See
[`ML_PIPELINE.md`](ML_PIPELINE.md) for the exact workflow and limitations.

## 17. GIS pipeline

Study bbox → OSMnx `graph_from_bbox` walk → NetworkX graph → edge lengths → attach heat to edges → cache as GraphML/GeoPackage under `data/processed`.

## 18. Routing pipeline

Candidates via weighted shortest path.
`cost = α * dist_norm + β * heat_norm + γ * time_norm`
Weights are **experimental**, not universally optimal.

The local prototype also exposes `POST /api/routes`, which returns one
GeoJSON candidate for each of the `shortest`, `balanced`, and `cooler` modes,
including distance, estimated walking time, heat estimates, and high-risk
segment share. These candidates can coincide when the same streets minimize
all three experimental costs.

`GET /api/history?limit=30` returns recent saved route candidates. The dashboard
groups comparison candidates into one search, and
`DELETE /api/history/<search_id>` removes all candidates from that search.
Successful `POST /api/route` and `POST /api/routes` requests save route history.

## 19. Security

`.env` for any future keys; `.gitignore` already ignores it. Validate lat/lon. Limit bbox size and request body size. Add browser security headers, use generic 500 messages, and keep secrets out of `static/js`. See [`SECURITY.md`](SECURITY.md) for the current local-development protections and limits.

## 20. Testing

Unit and API checks are implemented under `tests/`. See [`TESTING.md`](TESTING.md)
for the local run command and coverage. Full map and external-service checks
remain manual so the test suite does not depend on internet access or OSM downloads.

The current endpoint reference, request examples, and response/error formats are
documented in [`API.md`](API.md). The trained model has a synthetic-demo prediction
endpoint; it remains separate from the map heat layer and route costs.

The validation boundaries and future ground-truth collection protocol are in
[`VALIDATION.md`](VALIDATION.md). No real-world accuracy claim is made without
independent sensor observations.

The optional sensor architecture is documented in [`IOT_EXTENSION.md`](IOT_EXTENSION.md).
It is a future extension; the base app does not ingest sensor data.

## Limitations (must say in viva)

- Hyper-local heat without dense sensors is **estimated**, not measured.
- OSM completeness varies.
- Walking time is an estimate (e.g. 5 km/h).
- Risk bands are **project-defined**, not medical classifications.
- Prototype may use synthetic labels for ML demonstration.
