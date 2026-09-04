"""Tests for phone alignment (device -> world frame)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.calibration.phone_alignment import (
    PRESET_CONVENTIONS,
    PhoneAligner,
    alignment_metadata,
    compose_transforms,
    get_preset,
    validate_quaternion,
    validate_rotation_matrix,
)


def test_all_presets_have_valid_rotation_matrices():
    for name, convention in PRESET_CONVENTIONS.items():
        R = convention.to_rotation_matrix()
        assert validate_rotation_matrix(R), name
        assert validate_quaternion(convention.to_quaternion()), name
        assert convention.to_quaternion().shape == (4,)


def test_identity_preset_is_identity():
    aligner = PhoneAligner.from_preset("TOP_NORTH_SCREEN_UP")
    assert np.allclose(aligner.align_single([1.0, 2.0, 3.0]), [1.0, 2.0, 3.0])


def test_east_preset_top_points_east():
    aligner = PhoneAligner.from_preset("TOP_EAST_SCREEN_UP")
    top = aligner.align_single([0.0, 1.0, 0.0])  # device top (device +Y)
    assert np.allclose(top, [1.0, 0.0, 0.0], atol=1e-9)  # world East (+X)


def test_south_preset_rotates():
    aligner = PhoneAligner.from_preset("TOP_SOUTH_SCREEN_UP")
    top = aligner.align_single([0.0, 1.0, 0.0])
    assert np.allclose(top, [0.0, -1.0, 0.0], atol=1e-9)


def test_inverse_roundtrip_random_vectors():
    rng = np.random.default_rng(4)
    aligner = PhoneAligner.from_preset("TOP_UP_SCREEN_NORTH")
    for _ in range(10):
        v = rng.normal(size=3)
        w = aligner.align_single(v)
        back = aligner.align_inverse(w)
        assert np.allclose(back, v, atol=1e-9)


def test_align_vectors_batch_keeps_nan():
    aligner = PhoneAligner.from_preset("TOP_EAST_SCREEN_UP")
    v = np.array([[1.0, 0.0, 0.0], [np.nan, 1.0, 2.0], [0.0, 0.0, 1.0]])
    out = aligner.align_vectors(v)
    assert np.allclose(out[0], aligner.align_single([1.0, 0.0, 0.0]))
    assert np.isnan(out[1]).all()
    assert np.isfinite(out[2]).all()
    assert out.shape == v.shape


def test_align_dataframe_appends_columns_and_keeps_raw():
    aligner = PhoneAligner.from_preset("TOP_EAST_SCREEN_UP")
    df = pd.DataFrame({
        "accel_x": [1.0, 2.0], "accel_y": [0.0, 0.0], "accel_z": [9.8, 9.8],
        "gyro_x": [0.0, 0.0], "gyro_y": [1.0, 1.0], "gyro_z": [0.0, 0.0],
    })
    out, meta = aligner.align_dataframe(df)
    assert "accel_x_aligned" in out.columns
    assert out["accel_x"].tolist() == [1.0, 2.0]  # raw preserved
    assert meta["world_frame"] == "ENU"


def test_metadata_describes_transform():
    convention = get_preset("TOP_EAST_SCREEN_UP")
    meta = alignment_metadata(convention, applied_to=["accel_x", "accel_y", "accel_z"])
    assert meta["convention"]["name"] == "TOP_EAST_SCREEN_UP"
    assert meta["euler_order"].startswith("R = Rz(yaw)")
    assert meta["applied_to"] == ["accel_x", "accel_y", "accel_z"]


def test_compose_identity_then_east_is_east():
    identity = get_preset("TOP_NORTH_SCREEN_UP")
    east = get_preset("TOP_EAST_SCREEN_UP")
    composed = compose_transforms(identity, east)
    assert np.allclose(composed.to_quaternion(), east.to_quaternion(), atol=1e-9)


def test_unknown_preset_raises():
    with pytest.raises(KeyError):
        get_preset("NOPE")