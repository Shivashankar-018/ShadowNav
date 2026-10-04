"""Evaluate the selected synthetic model once on the held-out test split."""

import json

import joblib
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

import config
from ml.preprocess import FEATURES, SAMPLE_DATASET_PATH, TARGET, load_synthetic_dataset, split_dataset
from ml.train_model import MODEL_PATH

TEST_METRICS_PATH = config.BASE_DIR / "data" / "processed" / "synthetic_test_metrics.json"


def main() -> None:
    if not SAMPLE_DATASET_PATH.exists():
        raise FileNotFoundError("Sample dataset not found. Run: python -m ml.create_sample_dataset")
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Trained model not found. Run: python -m ml.train_model")

    dataset = load_synthetic_dataset()
    test = split_dataset(dataset).test
    artifact = joblib.load(MODEL_PATH)
    predictions = artifact["model"].predict(test[list(FEATURES)])
    report = {
        "data_source": artifact["data_source"],
        "model_name": artifact["model_name"],
        "test_rows": int(len(test)),
        "mae_c": float(mean_absolute_error(test[TARGET], predictions)),
        "rmse_c": float(root_mean_squared_error(test[TARGET], predictions)),
        "r2": float(r2_score(test[TARGET], predictions)),
        "disclaimer": artifact["disclaimer"],
    }
    TEST_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEST_METRICS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("These scores describe only agreement with the synthetic formula, not real heat accuracy.")
    print(f"Saved test results: {TEST_METRICS_PATH}")


if __name__ == "__main__":
    main()
