# ShadowNav API Reference

Base address for local development: `http://127.0.0.1:5000`

All endpoints below are implemented by the current Flask application. JSON
errors use this shape:

```json
{
  "ok": false,
  "error": "A readable explanation of the problem."
}
```

The prototype is intended for local development. It has no login, authentication,
or rate limiting. The Flask server binds to `127.0.0.1` by default, limits
request bodies to 16 KB, and adds basic browser security headers. Do not expose it
directly to the public internet; see [`SECURITY.md`](SECURITY.md).

When `SHADOWNAV_PUBLIC_DEMO=true`, history endpoints return an empty list with
`history_enabled: false`, route/prediction requests do not save history, and
delete-history endpoints return HTTP `403`. This mode is intended for the
public demo configuration; it does not add authentication or rate limiting.

## Endpoints

| Method | URL | Purpose |
|---|---|---|
| GET | `/api/status` | Return backend health and current development step. |
| GET | `/api/weather` | Return normalized Open-Meteo current weather. |
| POST | `/api/predict` | Run the locally trained, synthetic-only ML demonstration model. |
| GET | `/api/ml/metrics` | Return saved validation and test metrics for the synthetic model demo. |
| GET | `/api/predictions` | List recent locally saved synthetic demo predictions. |
| DELETE | `/api/predictions/<prediction_id>` | Delete one synthetic demo prediction-history entry. |
| GET | `/api/heatmap` | Return prototype heat estimates as GeoJSON. |
| GET | `/api/roads` | Return walking streets and prototype edge estimates as GeoJSON. |
| POST | `/api/route` | Calculate and save one preference-mode route. |
| POST | `/api/routes` | Calculate and save shortest, balanced, and cooler candidates. |
| GET | `/api/history` | List saved route candidates from local SQLite. |
| DELETE | `/api/history/<search_id>` | Delete one route search and all of its candidates. |

The homepage is `GET /`; the styled status page is `GET /status`.

## GET `/api/status`

No input. Returns HTTP `200` when the Flask application is responding.

```json
{
  "ok": true,
  "app": "ShadowNav",
  "message": "ShadowNav backend is running",
  "time_utc": "ISO-8601 timestamp",
  "step": 31
}
```

Sensor ingestion is a future extension. This version does not implement a
sensor-observation endpoint or accept ESP32/MQTT data.

## POST `/api/predict`

Runs the local trained model demonstration. Send a JSON object with a `features`
object containing all seven finite numeric inputs used by the synthetic
pipeline. Example inputs are synthetic-like demo values; the endpoint does not
fetch weather or associate them with a real map location. Its output is not
used by the heatmap or route planner.

```json
{
  "features": {
    "air_temperature_c": 30,
    "relative_humidity_percent": 55,
    "solar_radiation_wm2": 400,
    "wind_speed_kmh": 8,
    "distance_to_centre_km": 0.5,
    "vegetation_proxy": 0.4,
    "building_density_proxy": 0.6
  }
}
```

On success, HTTP `200` returns the estimated value, model name, source label,
disclaimer, and whether the result was saved to local synthetic prediction
history. The numeric response below is illustrative and will depend on the
trained artifact:

```json
{
  "ok": true,
  "estimated_heat_c": 31.25,
  "model_name": "linear_regression",
  "data_source": "synthetic",
  "disclaimer": "Synthetic teaching model; not validated against real street-temperature observations.",
  "prediction_id": "0123456789abcdef0123456789abcdef",
  "history_saved": true
}
```

Errors: `400` for missing or invalid features, `503` if the model has not been
trained (`python -m ml.train_model`), and `500` for an unexpected prediction
failure. This is a teaching demonstration, not a real-location heat estimate.

## GET `/api/predictions`

Optional `limit` query parameter from 1 to 100; defaults to 20. Returns saved
prediction IDs, UTC timestamps, model names, synthetic features, estimates, and
disclaimers. The local database stores no map coordinates or user identity for
these demo runs. Errors: `400` for an invalid limit; `500` if local history
cannot be read.

## DELETE `/api/predictions/<prediction_id>`

Deletes one locally stored synthetic demo run using its 32-character generated
hex ID. Returns the number of deleted rows. Errors: `400` for a malformed ID,
`404` if it was not found, and `500` if local history could not be updated.

## GET `/api/ml/metrics`

No input. Reads the validation and test JSON reports created by the training
workflow and returns the selected model, candidate validation MAEs, held-out
test MAE/RMSE/R², test row count, and a synthetic-data disclaimer. The values
are the saved results of the user's local run and can change when the dataset
or random seed changes.

Errors: `503` if either report is missing (run the sample generation, training,
and evaluation commands in `docs/ML_PIPELINE.md`); `500` if a report cannot be
read or has an invalid format. This endpoint supplies the homepage's saved
evaluation panel. Its metrics do not describe real-world heat prediction.

## GET `/api/weather`

Optional query parameters: `lat` and `lon`. If omitted, the configured map
centre is used. Coordinates must be numeric, with latitude in `[-90, 90]` and
longitude in `[-180, 180]`.

Success returns HTTP `200` with normalized fields including `temperature_c`,
`apparent_temperature_c`, `relative_humidity_percent`, `wind_speed_kmh`,
`cloud_cover_percent`, `precipitation_mm`, `shortwave_radiation_wm2`,
`weather_condition`, `timestamp`, and `units`. Values are weather-model grid
data, not street-level measurements.

Errors: `400` for invalid coordinates; `502` when the upstream weather service
is unavailable, times out, or returns unusable data.

Example:

```text
GET /api/weather?lat=12.9716&lon=77.5946
```

Selected response fields (sample values are illustrative and will vary):

```json
{
  "ok": true,
  "provider": "open-meteo",
  "cached": false,
  "latitude": 12.9716,
  "longitude": 77.5946,
  "elevation_m": 920,
  "timezone": "Asia/Calcutta",
  "timestamp": "2026-10-03T12:00",
  "temperature_c": 30.0,
  "apparent_temperature_c": 31.0,
  "relative_humidity_percent": 55,
  "wind_speed_kmh": 8.0,
  "wind_direction_deg": 220,
  "cloud_cover_percent": 20,
  "precipitation_mm": 0.0,
  "shortwave_radiation_wm2": 400.0,
  "weather_code": 1,
  "weather_condition": "Mainly clear",
  "units": {
    "temperature_c": "°C",
    "relative_humidity_percent": "%",
    "wind_speed_kmh": "km/h"
  },
  "note": "These values come from a weather model grid, not a street thermometer."
}
```

## GET `/api/heatmap`

Optional `lat` and `lon` query parameters use the same rules as `/api/weather`.
Returns HTTP `200` with a GeoJSON `FeatureCollection`. Each cell includes
`estimated_temp_c`, `base_temp_c`, `uhi_proxy_c`, `solar_bump_c`, `heat_risk`,
`color`, `timestamp`, and `method`. The response also includes `legend`,
`cell_count`, and a disclaimer. The spatial UHI offset is a prototype proxy;
the endpoint does not return measured street temperatures.

Errors: `400` for invalid coordinates; `502` if required weather data cannot be
obtained or used.

Abbreviated response shape (the running app returns its full configured grid):

```json
{
  "ok": true,
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "estimated_temp_c": 31.2,
        "base_temp_c": 30.0,
        "uhi_proxy_c": 1.2,
        "heat_risk": "Moderate",
        "color": "#abdda4",
        "method": "prototype-uhi-offset"
      },
      "geometry": { "type": "Polygon", "coordinates": [] }
    }
  ],
  "cell_count": 64,
  "disclaimer": "Prototype heat-risk estimate; not a street measurement."
}
```

## GET `/api/roads`

Optional `lat` and `lon` query parameters select the study-area centre and use
the same coordinate bounds. Returns HTTP `200` with walking-network GeoJSON.
Each edge feature has a `LineString` geometry and properties such as `name`,
`highway`, `length_m`, `estimated_temp_c`, and `heat_risk`. The response also
reports `edge_count`, `node_count`, and whether the network cache is in use.

Errors: `400` for invalid coordinates; `502` if the walking network or needed
weather data cannot be loaded.

Abbreviated response shape:

```json
{
  "ok": true,
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "name": "unnamed path",
        "highway": "residential",
        "length_m": 120.0,
        "estimated_temp_c": 31.2,
        "heat_risk": "Moderate"
      },
      "geometry": { "type": "LineString", "coordinates": [] }
    }
  ],
  "edge_count": 1,
  "node_count": 2,
  "cached": true
}
```

## POST `/api/route`

Send a JSON object with four required numeric coordinates and an optional mode.
Coordinates must be finite, must not be JSON booleans, and must be within
normal latitude/longitude bounds. They must also fall inside the configured
study area. `mode` may be `shortest`,
`balanced`, or `cooler`; if omitted, it defaults to `balanced`.

Request:

```json
{
  "source_lat": 12.98656,
  "source_lon": 77.58151,
  "destination_lat": 12.9598,
  "destination_lon": 77.60556,
  "mode": "balanced"
}
```

Success returns HTTP `200` with a GeoJSON `Feature`, its `mode`, route
`properties` (distance, estimated time, estimated heat, exposure proxy, and
high-risk segment share), `history_id`, and `history_saved`. If history storage
fails, the route can still be returned with `history_saved: false`.

Errors: `400` for missing, malformed, or out-of-range input; `422` when points
are outside the study area or no route can be calculated; `502` for a required
weather or network service failure.

Abbreviated successful response shape (numeric values are illustrative):

```json
{
  "ok": true,
  "type": "Feature",
  "mode": "balanced",
  "geometry": { "type": "LineString", "coordinates": [] },
  "properties": {
    "distance_km": 1.23,
    "estimated_time_min": 14.8,
    "average_estimated_temp_c": 31.2,
    "maximum_estimated_temp_c": 32.1,
    "heat_exposure_degree_km": 13.8,
    "high_risk_segment_percent": 2.0
  },
  "history_id": "32-character-hex-id",
  "history_saved": true
}
```

## POST `/api/routes`

Send the same four required coordinates as `/api/route`; no `mode` is needed.
Returns HTTP `200` with a `routes` object keyed by `shortest`, `balanced`, and
`cooler`, plus `history_id` and `history_saved`. Each candidate contains a
GeoJSON route and its own metrics. Candidates may use the same streets.

Errors: `400` for invalid input; `422` when a valid route cannot be calculated;
`502` for a required weather or network service failure.

Abbreviated response shape:

```json
{
  "ok": true,
  "routes": {
    "shortest": { "type": "Feature", "mode": "shortest", "geometry": {}, "properties": {} },
    "balanced": { "type": "Feature", "mode": "balanced", "geometry": {}, "properties": {} },
    "cooler": { "type": "Feature", "mode": "cooler", "geometry": {}, "properties": {} }
  },
  "history_id": "32-character-hex-id",
  "history_saved": true
}
```

## GET `/api/history`

Optional `limit` query parameter defaults to `30` and must be an integer from
`1` to `100`. Returns HTTP `200` with an `items` array. Each item includes the
search ID, timestamp, endpoints, mode, route metrics, and saved GeoJSON
geometry. Comparison candidates from one request share a `search_id`.

Errors: `400` for an invalid limit; `500` if local history cannot be read.

Abbreviated response shape:

```json
{
  "ok": true,
  "items": [
    {
      "search_id": "32-character-hex-id",
      "created_at": "ISO-8601 timestamp",
      "source_lat": 12.98656,
      "source_lon": 77.58151,
      "destination_lat": 12.9598,
      "destination_lon": 77.60556,
      "mode": "balanced",
      "distance_km": 1.23,
      "estimated_time_min": 14.8,
      "geometry": { "type": "LineString", "coordinates": [] }
    }
  ]
}
```

## DELETE `/api/history/<search_id>`

`search_id` must be the 32-character lowercase hexadecimal ID returned by a
route response or the history API. Deletes every candidate belonging to that
search.

Success returns HTTP `200` with `{"ok": true, "deleted_count": 1}` for a
single-route search, or a larger count for a route comparison. Errors: `400`
for an invalid ID; `404` if no saved search matches; `500` if local history
cannot be updated.

Example success JSON:

```json
{
  "ok": true,
  "deleted_count": 3
}
```

## PowerShell examples

Read recent history:

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:5000/api/history?limit=10"
```

Request one balanced route (this saves a local history entry):

```powershell
$body = @{
  source_lat = 12.98656
  source_lon = 77.58151
  destination_lat = 12.95980
  destination_lon = 77.60556
  mode = "balanced"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:5000/api/route" `
  -ContentType "application/json" `
  -Body $body
```

These sample coordinates are for the configured Bengaluru study area. Change
them only to points within the displayed study-area bounds.
