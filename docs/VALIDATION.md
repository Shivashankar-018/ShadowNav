# ShadowNav Validation Plan and Evidence

## Current validation status

| Validation layer | Current status | What the evidence means |
|---|---|---|
| Software/API | Partial manual checks completed; pytest execution has not been confirmed in this workspace | The local homepage and status endpoint have responded successfully. This does not establish heat-prediction accuracy. |
| Route calculation | A manual route request returned a walking path and metrics | This checks that the route pipeline returns a result for one pair of points; it does not prove every OSM path is complete or safe. |
| Geographic | Not independently ground-truthed | Roads and geometry come from OpenStreetMap; map alignment and coverage vary. |
| ML | Synthetic pipeline evaluated; real-world validation not performed | Saved metrics measure fit to generated demo labels. There is no independent labelled street-temperature dataset. |
| Real-world heat | Not performed | No calibrated field sensors or independent street-level observations have been supplied. |
| Performance | Not measured systematically | Record timings during a repeatable demo before reporting performance results. |

The current heat layer is a transparent prototype offset applied to model-grid
weather. It is not a trained ML prediction, a thermometer measurement, or
medical guidance. The risk labels are project-defined categories.

## Validation stages

### 1. Prototype/software validation

- Run the automated suite using [`TESTING.md`](TESTING.md), and record its real
  output. Do not call the test suite passed until it has been run successfully.
- Manually check the homepage, status endpoint, map, source/destination pins,
  route response, and route-history display.
- Record the date, browser, test coordinates, outcome, and any error for each
  manual check.

### 2. Geographic validation

- Check that each selected point lies in the displayed study-area boundary.
- Confirm that route endpoints snap to nearby walking-network nodes and that
  the returned line follows visible OpenStreetMap walking streets.
- Record cases with missing, disconnected, or misplaced road segments.
- Treat this as a geometry/network check only; visual agreement does not verify
  temperature or shade.

### 3. Real-world ML validation (future, after collecting observations)

- Use independently measured observations as labels. Do not use the prototype
  heat estimates as if they were ground truth.
- Keep observations from the same time window and location together when
  splitting data; reserve whole locations or time periods for holdout checks
  to reduce spatial and temporal leakage.
- Compare against a simple weather-only baseline and report MAE, RMSE, and R²
  on an untouched test set. Report dataset size, units, location coverage,
  collection times, and missing-data handling beside the metrics.
- Do not report model accuracy until the model has been trained and evaluated
  on real held-out observations.

The current Linear Regression, Random Forest, and Histogram Gradient Boosting
comparison is an internal synthetic-data demonstration. Its saved test scores
must not be described as real-world heat-prediction accuracy; see
[`ML_PIPELINE.md`](ML_PIPELINE.md).

### 4. Real-world heat validation (future)

- Collect air-temperature observations at known coordinates and timestamps
  using identified, checked sensors. Record measurement height, sensor model,
  calibration/check information, and quality notes.
- Compare a prediction for the same location and time with each accepted
  observation. Keep rejected or suspect readings flagged; do not silently
  remove them.
- Include a range of locations and observation times. A small pilot can check
  feasibility, but cannot establish city-wide performance.
- Store only environmental measurements and the minimum metadata needed for
  quality checks; do not collect walker identity or personal movement history.

## Ground-truth observation template

The blank file [`../data/sample/validation_observations_template.csv`](../data/sample/validation_observations_template.csv)
contains column names only. It has no sample measurements. Add rows only after
collecting real observations, and keep raw measurements distinct from
model-derived estimates.

| Column | Meaning |
|---|---|
| `observation_id` | Non-personal unique row identifier |
| `observed_at_utc` | Observation timestamp in ISO-8601 UTC |
| `latitude`, `longitude` | WGS84 observation location in decimal degrees |
| `air_temperature_c` | Sensor-observed air temperature in °C |
| `relative_humidity_percent` | Sensor-observed relative humidity (%) |
| `wind_speed_kmh` | Sensor-observed wind speed, if available |
| `sensor_height_m` | Height of the sensor above ground |
| `sensor_model` | Sensor make/model identifier |
| `calibration_reference` | Calibration or comparison note/reference |
| `quality_flag` | `valid`, `suspect`, or `rejected` |
| `notes` | Environmental or quality notes; no personal information |

## Results reporting rule

Only enter values measured or computed by an executed experiment. Mark planned
values as **not measured**. Keep software-function checks, geographic checks,
ML metrics, and real-world sensor comparisons as separate results.
