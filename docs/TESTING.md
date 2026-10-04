# ShadowNav Testing Guide

The local pytest suite checks heat-risk thresholds, weather-field parsing,
route-cost behavior, SQLite route and prediction history, API input validation,
response headers, request-size limits, and the API-to-database flow. Tests use deterministic
sample data and a temporary database; they do not overwrite
`data/shadownav.sqlite3` or call external services.

## Test case plan

| Area | Case | Verification |
|---|---|---|
| Unit | Heat-risk thresholds and centre estimate | Automated pytest checks |
| Unit | Open-Meteo field normalization | Automated pytest with sample JSON; no network call |
| Unit | Shortest, balanced, and cooler edge costs | Automated pytest checks cost ordering |
| Unit | SQLite route save, retrieval, grouping, and deletion | Automated pytest with a temporary database |
| Integration | Route API saves a deterministic route to history | Automated Flask test client; route calculation is stubbed |
| API | Invalid coordinates, modes, history IDs/limits, and oversized body | Automated Flask test client |
| UI | Map, source/destination pins, heat overlay, and route drawing | Manual browser check |
| Performance | Status, heatmap, and route response times | Measure and record during the demo; no measurements claimed here |
| API | Synthetic prediction endpoint response and required features field | Flask test client with prediction model stubbed |
| API | Saved synthetic metrics response and missing-report handling | Flask test client with metric loader stubbed |
| Database/API | Save, list, and delete synthetic prediction history | Temporary SQLite database and Flask test client |
| ML | Synthetic dataset labels and reproducible train/validation/test split | Automated pytest; no real observations or model accuracy claimed |

## Install the test dependency

From PowerShell in the project folder, with the virtual environment active:

```powershell
python -m pip install -r requirements.txt
```

`requirements.txt` includes pytest alongside the application dependencies.

## Run all tests

```powershell
python -m pytest -q
```

For names and individual results, use:

```powershell
python -m pytest -v
```

There are currently 30 test cases, including the parameterized heat-threshold
checks. A successful run should end with `30 passed`. If a test fails, read the
first `FAILED` item and its assertion message, then share that output to
troubleshoot it.

## What the suite does not test

The automated checks do not download OpenStreetMap data, call Open-Meteo, or
recalculate a route. Those services are network-dependent and can be slow or
unavailable. Check map rendering and a real route manually in the running app.
