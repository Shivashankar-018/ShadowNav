"""Create labelled teaching data; generated values are not observations."""

import argparse

import numpy as np
import pandas as pd

import config
from ml.preprocess import FEATURES, SAMPLE_DATASET_PATH, TARGET


def create_dataset(rows: int = 2500, seed: int = 42) -> pd.DataFrame:
    """Return reproducible synthetic samples from an arbitrary demo formula."""
    if rows < 30:
        raise ValueError("Choose at least 30 rows so all three data splits are meaningful.")
    rng = np.random.default_rng(seed)
    air_temperature = rng.uniform(18.0, 40.0, rows)
    humidity = rng.uniform(20.0, 90.0, rows)
    solar = rng.uniform(0.0, 950.0, rows)
    wind = rng.uniform(0.0, 22.0, rows)
    distance = rng.uniform(0.0, config.UHI_RADIUS_KM * 1.5, rows)
    vegetation = rng.uniform(0.0, 1.0, rows)
    building_density = rng.uniform(0.0, 1.0, rows)

    # Deliberately simple teaching formula. Its coefficients are illustrative,
    # not calibrated from sensors or claimed to represent urban physics.
    centre_offset = np.maximum(0.0, 1.0 - distance / (config.UHI_RADIUS_KM * 1.5))
    target = (
        air_temperature
        + centre_offset * config.UHI_MAX_OFFSET_C
        + solar * 0.002
        + (humidity - 50.0) * 0.008
        - vegetation * 1.2
        + building_density * 0.9
        - wind * 0.04
        + rng.normal(0.0, 0.3, rows)
    )
    return pd.DataFrame(
        {
            FEATURES[0]: air_temperature,
            FEATURES[1]: humidity,
            FEATURES[2]: solar,
            FEATURES[3]: wind,
            FEATURES[4]: distance,
            FEATURES[5]: vegetation,
            FEATURES[6]: building_density,
            TARGET: target,
            "data_source": "synthetic",
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2500, help="Number of simulated rows (minimum 30).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for repeatable sample generation.")
    args = parser.parse_args()
    dataset = create_dataset(rows=args.rows, seed=args.seed)
    SAMPLE_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(SAMPLE_DATASET_PATH, index=False)
    print(f"Created {len(dataset)} synthetic teaching rows: {SAMPLE_DATASET_PATH}")
    print("These are simulated values, not measured temperatures or real-world observations.")


if __name__ == "__main__":
    main()
