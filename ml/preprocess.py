"""Load and split the explicitly synthetic heat-training sample."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

import config

FEATURES = (
    "air_temperature_c",
    "relative_humidity_percent",
    "solar_radiation_wm2",
    "wind_speed_kmh",
    "distance_to_centre_km",
    "vegetation_proxy",
    "building_density_proxy",
)
TARGET = "synthetic_heat_target_c"
DATA_SOURCE_COLUMN = "data_source"
SPLIT_SEED = 42
SAMPLE_DATASET_PATH = config.BASE_DIR / "data" / "sample" / "synthetic_heat_training.csv"


@dataclass(frozen=True)
class DatasetSplits:
    """Three disjoint data partitions; the test set stays untouched until evaluation."""

    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


def load_synthetic_dataset(path: str | Path = SAMPLE_DATASET_PATH) -> pd.DataFrame:
    """Read a sample CSV and reject missing, invalid, or non-synthetic targets."""
    dataset = pd.read_csv(path)
    required_columns = [*FEATURES, TARGET, DATA_SOURCE_COLUMN]
    missing_columns = sorted(set(required_columns) - set(dataset.columns))
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing_columns)}")
    if dataset.empty:
        raise ValueError("Dataset has no rows.")
    if dataset[DATA_SOURCE_COLUMN].isna().any() or set(dataset[DATA_SOURCE_COLUMN]) != {"synthetic"}:
        raise ValueError("This teaching pipeline accepts only rows labelled data_source='synthetic'.")

    numeric_values = dataset[[*FEATURES, TARGET]].apply(pd.to_numeric, errors="coerce")
    if numeric_values.isna().any().any():
        raise ValueError("Dataset contains missing or non-numeric feature/target values.")
    if not np.isfinite(numeric_values.to_numpy(dtype=float)).all():
        raise ValueError("Dataset contains non-finite feature/target values.")

    dataset = dataset.copy()
    dataset[[*FEATURES, TARGET]] = numeric_values
    return dataset


def split_dataset(dataset: pd.DataFrame) -> DatasetSplits:
    """Split rows 60/20/20 with fixed seeds, preserving original row indices."""
    if len(dataset) < 30:
        raise ValueError("At least 30 dataset rows are required for a 60/20/20 split.")
    train_validation, test = train_test_split(
        dataset, test_size=0.20, random_state=SPLIT_SEED, shuffle=True
    )
    train, validation = train_test_split(
        train_validation, test_size=0.25, random_state=SPLIT_SEED + 1, shuffle=True
    )
    return DatasetSplits(train=train, validation=validation, test=test)
