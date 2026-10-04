"""Read persisted synthetic-model evaluation reports for the local dashboard."""

import json

import config

VALIDATION_REPORT_PATH = (
    config.BASE_DIR / "data" / "processed" / "synthetic_validation_metrics.json"
)
TEST_REPORT_PATH = config.BASE_DIR / "data" / "processed" / "synthetic_test_metrics.json"
DISCLAIMER = (
    "These metrics describe performance on generated synthetic data only. "
    "They do not measure real street-temperature accuracy."
)


def load_ml_metrics() -> dict:
    """Load and validate both saved metric files for display and API output."""
    if not VALIDATION_REPORT_PATH.exists() or not TEST_REPORT_PATH.exists():
        raise FileNotFoundError(
            "ML reports are not ready. Run the sample-data, training, and evaluation commands."
        )

    with VALIDATION_REPORT_PATH.open(encoding="utf-8") as file:
        validation = json.load(file)
    with TEST_REPORT_PATH.open(encoding="utf-8") as file:
        test = json.load(file)

    if not isinstance(validation, dict) or not isinstance(test, dict):
        raise ValueError("The ML report files must contain JSON objects.")
    if validation.get("data_source") != "synthetic" or test.get("data_source") != "synthetic":
        raise ValueError("The dashboard accepts only reports labelled as synthetic.")
    if not isinstance(validation.get("validation_results"), dict):
        raise ValueError("The validation report has an invalid format.")
    required_test_fields = ("model_name", "test_rows", "mae_c", "rmse_c", "r2")
    if any(field not in test for field in required_test_fields):
        raise ValueError("The test report is missing required metrics.")

    return {
        "ok": True,
        "data_source": "synthetic",
        "selected_model": validation.get("selected_model"),
        "selection_metric": validation.get("selection_metric"),
        "validation_results": validation["validation_results"],
        "test_metrics": {field: test[field] for field in required_test_fields},
        "disclaimer": DISCLAIMER,
    }
