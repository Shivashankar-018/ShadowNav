"""Checks for synthetic labelling and deterministic, disjoint ML partitions."""

import pandas as pd

from ml.create_sample_dataset import create_dataset
from ml.preprocess import split_dataset


def test_synthetic_dataset_is_reproducible_and_clearly_labelled():
    first = create_dataset(rows=120, seed=17)
    second = create_dataset(rows=120, seed=17)

    pd.testing.assert_frame_equal(first, second)
    assert set(first["data_source"]) == {"synthetic"}
    assert "synthetic_heat_target_c" in first.columns


def test_train_validation_and_test_partitions_are_disjoint():
    splits = split_dataset(create_dataset(rows=120, seed=19))
    train_ids = set(splits.train.index)
    validation_ids = set(splits.validation.index)
    test_ids = set(splits.test.index)

    assert len(splits.train) == 72
    assert len(splits.validation) == 24
    assert len(splits.test) == 24
    assert train_ids.isdisjoint(validation_ids)
    assert train_ids.isdisjoint(test_ids)
    assert validation_ids.isdisjoint(test_ids)
