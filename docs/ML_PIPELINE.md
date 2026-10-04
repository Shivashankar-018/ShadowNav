# ShadowNav Synthetic ML Pipeline

## What this milestone provides

This guide documents the reproducible dataset generator, preprocessing and
data split, three regression baselines, validation-based model selection, a
held-out test report, and prediction helper. The model is exposed through a
separate synthetic-demo API and homepage panel; it does not power the Flask
heatmap or route planner.

## Data and its limits

`python -m ml.create_sample_dataset` generates
`data/sample/synthetic_heat_training.csv`. Every row is explicitly marked
`data_source=synthetic`. Weather-like input columns, spatial proxy columns, and
the target are all generated for this teaching pipeline; they are not live
weather observations, sensor measurements, satellite data, or surveyed land
cover. The target comes from a deliberately simple arbitrary formula in
`ml/create_sample_dataset.py` plus random noise. It is not a physical heat model.

The model's only purpose here is to demonstrate a sound coding workflow. Low
error on these rows means it approximates the formula that generated them. It
does not demonstrate accuracy for Bengaluru streets or any other real place.
The current map layer remains the separately labelled proxy documented in
`docs/VALIDATION.md`.

## Feature dictionary

| Feature | Meaning in this pipeline | Status |
|---|---|---|
| `air_temperature_c` | Generated air-temperature-like input | Synthetic, not observed |
| `relative_humidity_percent` | Generated humidity-like input | Synthetic, not observed |
| `solar_radiation_wm2` | Generated solar-radiation-like input | Synthetic, not observed |
| `wind_speed_kmh` | Generated wind-speed-like input | Synthetic, not observed |
| `distance_to_centre_km` | Generated distance proxy | Synthetic location proxy |
| `vegetation_proxy` | Value from 0 to 1 | Synthetic proxy; not derived from imagery or a GIS layer |
| `building_density_proxy` | Value from 0 to 1 | Synthetic proxy; not derived from building footprints |
| `synthetic_heat_target_c` | Teaching target from the arbitrary formula | Synthetic; not measured temperature |

The live weather service and OSM data are not used in this dataset or model.
This avoids implying that a real-world target exists when none has been
collected. A future real model needs time- and location-matched ground-truth
observations, documented spatial/temporal resolution, and a leakage-safe split
that holds out locations or time periods.

## Split and model selection

The fixed-seed split is 60% training, 20% validation, and 20% test. Candidate
models are ordinary least-squares Linear Regression, Random Forest, and
Histogram Gradient Boosting. The lowest validation MAE selects the candidate.
That model is then refit on training plus validation rows. The test rows are
used only by the separate evaluation command. Fixed seeds help reproduce this
small demonstration. See the official scikit-learn documentation for
[`train_test_split`](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html),
[regression evaluation metrics](https://scikit-learn.org/stable/modules/model_evaluation.html),
and [Histogram Gradient Boosting](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html).

## Windows / PowerShell commands

Open PowerShell in the ShadowNav project folder and activate the environment
if it is not already active:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run the workflow in order:

```powershell
python -m ml.create_sample_dataset
python -m ml.train_model
python -m ml.evaluate_model
python -m ml.predict
```

You can choose a different sample size and seed, for example:

```powershell
python -m ml.create_sample_dataset --rows 3000 --seed 42
```

The prediction helper uses a fixed example input from the same synthetic
feature ranges. Its result is a model output, not a real location reading.

## Generated files

- `data/sample/synthetic_heat_training.csv`: generated rows; this local CSV is
  excluded from Git and can be regenerated with the documented command.
- `models/shadownav_synthetic_heat_model.joblib`: locally serialized estimator.
- `data/processed/synthetic_validation_metrics.json`: candidate validation MAE.
- `data/processed/synthetic_test_metrics.json`: final MAE, RMSE, and R² for the
  held-out synthetic test split.

The model and processed data paths are ignored by Git. Record actual command
outputs in a project report only after running them; do not copy example or
invented metrics into the results chapter. These reports must retain their
synthetic-data disclaimer.

## Current integration boundary

`ml/predict.py` exposes a Python helper and validates its feature inputs.
`POST /api/predict` and the homepage's ML demonstration panel call that helper
using explicitly labelled demo inputs. `GET /api/ml/metrics` reads the saved
validation and test JSON reports for the results panel. These demonstrations
remain separate from the live weather panel, heatmap, and route costs, which
still use the existing weather service and labelled prototype proxy. Do not
describe the demo output as a prediction for a real map location or use it to
claim real street-level accuracy.
