"""Compare regression models on synthetic data and select by validation MAE."""

import json

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import config
from ml.preprocess import FEATURES, SAMPLE_DATASET_PATH, TARGET, load_synthetic_dataset, split_dataset

MODEL_PATH = config.BASE_DIR / "models" / "shadownav_synthetic_heat_model.joblib"
VALIDATION_METRICS_PATH = config.BASE_DIR / "data" / "processed" / "synthetic_validation_metrics.json"
DISCLAIMER = "Synthetic teaching model; not validated against real street-temperature observations."


def build_candidates():
    """Return small, reproducible baseline regressors for local demonstration."""
    return {
        "linear_regression": make_pipeline(StandardScaler(), LinearRegression()),
        "random_forest": RandomForestRegressor(
            n_estimators=120, min_samples_leaf=2, random_state=42, n_jobs=-1
        ),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            max_iter=120, max_leaf_nodes=15, random_state=42
        ),
    }


def main() -> None:
    if not SAMPLE_DATASET_PATH.exists():
        raise FileNotFoundError("Sample dataset not found. Run: python -m ml.create_sample_dataset")
    dataset = load_synthetic_dataset()
    splits = split_dataset(dataset)
    scores = {}
    best_name = None
    best_model = None
    best_mae = float("inf")

    for name, model in build_candidates().items():
        model.fit(splits.train[list(FEATURES)], splits.train[TARGET])
        validation_mae = float(
            mean_absolute_error(
                splits.validation[TARGET],
                model.predict(splits.validation[list(FEATURES)]),
            )
        )
        scores[name] = {"validation_mae_c": validation_mae}
        print(f"{name}: validation MAE = {validation_mae:.4f} °C (synthetic data)")
        if validation_mae < best_mae:
            best_name, best_model, best_mae = name, model, validation_mae

    # The test partition is excluded from model choice; refit using train + validation.
    train_validation = pd.concat([splits.train, splits.validation])
    best_model.fit(train_validation[list(FEATURES)], train_validation[TARGET])
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": best_model,
            "model_name": best_name,
            "features": list(FEATURES),
            "target": TARGET,
            "data_source": "synthetic",
            "disclaimer": DISCLAIMER,
        },
        MODEL_PATH,
    )
    report = {
        "data_source": "synthetic",
        "selected_model": best_name,
        "selection_metric": "validation_mae_c",
        "validation_results": scores,
        "disclaimer": DISCLAIMER,
    }
    VALIDATION_METRICS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Selected by validation MAE: {best_name}")
    print(f"Saved trained artifact: {MODEL_PATH}")
    print(f"Saved validation results: {VALIDATION_METRICS_PATH}")
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
