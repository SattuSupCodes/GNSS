"""Typed configuration for Phase 3 GNSS blackout simulations.

Mirrors ``configs/evaluation_config.yaml`` and provides ``from_dict`` so the
CLI can load YAML into validated dataclasses (mirroring the Phase 2 pattern of
``CalibrationConfig`` / ``PipelineConfig``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .gnss_blackout import GNSS_FIELDS

DEFAULT_DURATIONS_S: List[float] = [5.0, 10.0, 20.0, 30.0, 60.0, 120.0]


@dataclass
class BlackoutConfig:
    durations_s: List[float] = field(default_factory=lambda: list(DEFAULT_DURATIONS_S))
    seed: int = 2024
    n_scenarios_per_duration: int = 1
    n_intervals_per_scenario: int = 1
    min_trip_duration_s: float = 30.0
    min_pre_blackout_s: float = 5.0
    min_post_blackout_s: float = 5.0
    min_gap_between_blackouts_s: float = 0.0
    allow_overlap: bool = False
    mask_columns: List[str] = field(default_factory=lambda: list(GNSS_FIELDS))
    availability_column: str = "gnss_available"
    phase_column: str = "blackout_phase"
    blackout_id_column: str = "blackout_id"


@dataclass
class ReferenceConfig:
    attach_vehicle_reference: bool = True
    root: str = "data/processed/synchronized"
    file_pattern: str = "trip_{trip_id}_vehicle_reference.parquet"
    columns: Dict[str, str] = field(
        default_factory=lambda: {
            "reference_latitude_deg": " Latitude (degrees)",
            "reference_longitude_deg": " Longitude (degrees)",
            "reference_speed_kmh": " Velocity (km/hr)",
            "reference_heading_deg": " Heading (degrees)",
            "reference_height_m": " Height (km)",
        }
    )
    availability_column: str = "reference_available"
    source_column: str = "reference_source"


@dataclass
class OutputConfig:
    format: str = "parquet"
    root: str = "data/blackout"
    duration_subdir_pattern: str = "{duration_s}s"
    trip_file_pattern: str = "{scenario_id}.parquet"
    metadata_file_pattern: str = "{scenario_id}_metadata.json"
    index_file: str = "scenarios_index.json"

    def duration_dir(self, duration_s: float) -> str:
        return self.duration_subdir_pattern.format(duration_s=f"{duration_s:g}")


@dataclass
class InputConfig:
    source: str = "calibrated"


@dataclass
class EvaluationConfig:
    blackout: BlackoutConfig = field(default_factory=BlackoutConfig)
    reference: ReferenceConfig = field(default_factory=ReferenceConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    input: InputConfig = field(default_factory=InputConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationConfig":
        data = data or {}
        return cls(
            blackout=BlackoutConfig(**data.get("blackout", {})),
            reference=ReferenceConfig(**data.get("reference", {})),
            output=OutputConfig(**data.get("output", {})),
            input=InputConfig(**data.get("input", {})),
        )

    def to_dict(self) -> dict:
        return {
            "blackout": self.blackout.__dict__,
            "reference": self.reference.__dict__,
            "output": self.output.__dict__,
            "input": self.input.__dict__,
        }