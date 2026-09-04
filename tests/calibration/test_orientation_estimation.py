"""Tests for quaternion toolkit + orientation estimation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.calibration.orientation_estimation import (
    OrientationEstimator,
    ORIENTATION_COLUMNS,
    is_rotation_matrix,
    magnetometer_heading_from_horizontal,
    magnetometer_quality,
    quat_from_axis_angle,
    quat_from_euler,
    quat_from_rotation_matrix,
    quat_from_two_vectors,
    quat_multiply,
    quat_normalize,
    quat_rotate,
    quat_to_euler,
    quat_to_rotation_matrix,
    quat_conjugate,
    roll_pitch_from_gravity,
    slerp,
    tilt_compensated_magnetometer,
)


def test_quat_rotate_90deg_about_z():
    q = quat_from_axis_angle([0.0, 0.0, 1.0], np.pi / 2)
    v = quat_rotate(q, [1.0, 0.0, 0.0])
    assert np.allclose(v, [0.0, 1.0, 0.0], atol=1e-9)
    back = quat_rotate(q, v, inverse=True)
    assert np.allclose(back, [1.0, 0.0, 0.0], atol=1e-9)


def test_quat_from_matrix_roundtrip_random():
    rng = np.random.default_rng(0)
    for _ in range(10):
        axis = rng.normal(size=3)
        angle = rng.uniform(-np.pi, np.pi)
        q = quat_from_axis_angle(axis, angle)
        R = quat_to_rotation_matrix(q)
        assert is_rotation_matrix(R)
        q2 = quat_from_rotation_matrix(R)
        assert np.allclose(abs(np.dot(q, q2)), 1.0, atol=1e-6)


def test_euler_roundtrip():
    yaw, pitch, roll = np.radians([30.0, 10.0, 5.0])
    q = quat_from_euler(yaw, pitch, roll)
    assert np.linalg.norm(q) == pytest.approx(1.0)
    y2, p2, r2 = quat_to_euler(q)
    assert np.allclose([y2, p2, r2], [yaw, pitch, roll], atol=1e-9)


def test_two_vectors_rotates_a_onto_b():
    rng = np.random.default_rng(1)
    for _ in range(10):
        a = rng.normal(size=3)
        b = rng.normal(size=3)
        q = quat_from_two_vectors(a, b)
        assert np.allclose(quat_rotate(q, a / np.linalg.norm(a)),
                           b / np.linalg.norm(b), atol=1e-9)


def test_quat_conjugate_inverse_rotation():
    q = quat_from_euler(0.4, -0.3, 0.2)
    v = np.array([1.0, -2.0, 3.0])
    assert np.allclose(quat_rotate(quat_conjugate(q), quat_rotate(q, v)), v)


def test_roll_pitch_flat_gravity_zero():
    roll, pitch = roll_pitch_from_gravity(np.array([0.0]), np.array([0.0]), np.array([9.8]))
    assert float(roll[0]) == pytest.approx(0.0, abs=1e-9)
    assert float(pitch[0]) == pytest.approx(0.0, abs=1e-9)


def test_roll_pitch_tilted():
    deg = np.pi / 6
    g = np.array([-9.8 * np.sin(deg), 0.0, 9.8 * np.cos(deg)])
    roll, pitch = roll_pitch_from_gravity(g[0:1], g[1:2], g[2:3])
    assert float(roll[0]) == pytest.approx(0.0, abs=1e-9)
    assert float(pitch[0]) == pytest.approx(deg, abs=1e-9)


def test_magnetometer_heading_equals_body_yaw_level():
    body_yaw = np.radians(37.0)
    north, down = 25.0, -35.0  # muT horizontal + vertical dip
    R = quat_to_rotation_matrix(quat_from_axis_angle([0.0, 0.0, 1.0], body_yaw))
    # world mag field (north, east=0, down); device = R^T * world
    world = np.array([0.0, north, down])
    dev = R.T @ world
    roll = np.array([0.0])
    pitch = np.array([0.0])
    hx, hy, _ = tilt_compensated_magnetometer(
        np.array([dev[0]]), np.array([dev[1]]), np.array([dev[2]]), roll, pitch
    )
    yaw = magnetometer_heading_from_horizontal(hx, hy)[0]
    assert float(yaw) == pytest.approx(body_yaw, abs=1e-9)


def test_magnetometer_quality_band():
    q = magnetometer_quality(np.array([25.0, 5.0, 1000.0, np.nan]))
    assert list(q) == ["high", "low", "low", "unavailable"]


def test_slerp_endpoints():
    a = quat_from_axis_angle([0.0, 0.0, 1.0], 0.0)
    b = quat_from_axis_angle([0.0, 0.0, 1.0], np.pi / 2)
    assert np.allclose(slerp(a, b, 0.0), a)
    assert np.allclose(slerp(a, b, 1.0), b, atol=1e-6)


def _level_frame(n=121):
    rng = np.random.default_rng(3)
    accel = np.column_stack([
        rng.normal(0.0, 0.01, n),
        rng.normal(0.0, 0.01, n),
        np.full(n, 9.8),
    ])
    gyro = np.zeros((n, 3))
    # magnetometer: north 25 uT, vertical dip -35 uT, small noise
    mag = np.column_stack([
        rng.normal(0.0, 0.5, n),
        rng.normal(25.0, 0.5, n),
        rng.normal(-35.0, 0.5, n),
    ])
    return pd.DataFrame(
        np.column_stack([np.arange(n) / 10.0, accel, gyro, mag]),
        columns=["timestamp", "accel_x", "accel_y", "accel_z",
                 "gyro_x", "gyro_y", "gyro_z", "mag_x", "mag_y", "mag_z"],
    )


def test_complementary_filter_flat_level():
    df = _level_frame()
    res = OrientationEstimator().estimate(df)
    last = res.frame.iloc[-1]
    assert last["orient_roll_deg"] == pytest.approx(0.0, abs=2.0)
    assert last["orient_pitch_deg"] == pytest.approx(0.0, abs=2.0)
    assert abs(last["orient_yaw_deg"]) <= 5.0
    assert last["orient_heading_source"] == "magnetometer"
    assert last["orient_heading_quality"] == "high"


def test_orientation_output_columns_present():
    df = _level_frame()
    res = OrientationEstimator().estimate(df)
    for c in ORIENTATION_COLUMNS:
        assert c in res.frame.columns
    assert res.frame["orient_qx"].apply(lambda v: np.linalg.norm([1.0, v, 0.0, 0.0])).notna().all()


def test_orientation_raw_not_modified():
    df = _level_frame()
    orig = df.copy()
    OrientationEstimator().estimate(df)
    pd.testing.assert_frame_equal(df, orig)