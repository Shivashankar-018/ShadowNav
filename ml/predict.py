"""Make a labelled prediction with the locally trained synthetic demonstration model."""

from collections.abc import Mapping
from math import isfinite
from numbers import Real

import joblib
import pandas as pd

from ml.preprocess import FEATURES
from ml.train_model import DISCLAIMER, MODEL_PATH


def _validated_features(values: Mapping) -> dict[str, float]:
    missing = [name for name in FEATURES if name not in values]
    if missing:
        raise ValueError(f"Missing required features: {', '.join(missing)}")
    clean = {}
    for name in FEATURES:
        value = values[name]
        if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
            raise ValueError(f"{name} must be a finite number.")
        clean[name] = float(value)

    if not 0 <= clean["relative_humidity_percent"] <= 100:
        raise ValueError("relative_humidity_percent must be between 0 and 100.")
    for name in ("solar_radiation_wm2", "wind_speed_kmh", "distance_to_centre_km"):
        if clean[name] < 0:
            raise ValueError(f"{name} cannot be negative.")
    for name in ("vegetation_proxy", "building_density_proxy"):
        if not 0 <= clean[name] <= 1:
            raise ValueError(f"{name} must be between 0 and 1.")
    return clean


def predict_heat(features: Mapping) -> dict:
    """Return a model estimate with its synthetic source and limitation attached."""
    clean = _validated_features(features)
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Trained model not found. Run: python -m ml.train_model")
    artifact = joblib.load(MODEL_PATH)
    row = pd.DataFrame([clean], columns=artifact["features"])
    estimate = float(artifact["model"].predict(row)[0])
    return {
        "estimated_heat_c": estimate,
        "model_name": artifact["model_name"],
        "data_source": artifact["data_source"],
        "disclaimer": artifact["disclaimer"],
    }


def main() -> None:
    example = {
        "air_temperature_c": 30.0,
        "relative_humidity_percent": 55.0,
        "solar_radiation_wm2": 400.0,
        "wind_speed_kmh": 8.0,
        "distance_to_centre_km": 0.5,
        "vegetation_proxy": 0.4,
        "building_density_proxy": 0.6,
    }
    result = predict_heat(example)
    print(result)
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
