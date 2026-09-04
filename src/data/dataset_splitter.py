"""Trip-level dataset splitting.

Splits are ALWAYS performed on complete trips, never on individual rows, to
avoid temporal/route leakage between train/validation/test. The splitter
operates on trip ids only and returns the assignment; it does not move data.

Given the current local dataset has 72 smartphone trips (synchronised), the
default split is ~70/15/15 when enough trips exist. When fewer than
``min_trips_per_split`` trips are available a warning is produced and the
train/val/test split will contain empty sets, which callers must handle.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence
import warnings

from .data_schema import TRIP_ID


@dataclass
class SplitResult:
    """Trip id -> split assignment plus diagnostics."""

    assignment: Dict[str, str] = field(default_factory=dict)
    train: List[str] = field(default_factory=list)
    validation: List[str] = field(default_factory=list)
    test: List[str] = field(default_factory=list)
    warned: bool = False

    def counts(self) -> Dict[str, int]:
        return {
            "train": len(self.train),
            "validation": len(self.validation),
            "test": len(self.test),
        }

    def split_for(self, trip_id: str) -> str:
        return self.assignment.get(trip_id, "unknown")


def split_trips_by_id(
    trip_ids: Sequence[str],
    ratios: Sequence[float] = (0.7, 0.15, 0.15),
    shuffle: bool = True,
    seed: Optional[int] = 42,
    min_trips_per_split: int = 1,
) -> SplitResult:
    """Split trip ids into train/validation/test.

    Parameters
    ----------
    trip_ids : sequence of trip ids.
    ratios : (train, validation, test) fractions summing to 1.
    shuffle : whether to shuffle trips before assignment.
    seed : RNG seed; ``None`` for true randomness.
    min_trips_per_split : minimum trips required in each split before a warning
        is emitted (not enforced as an error).

    Returns a :class:`SplitResult` with whole-trip assignment.
    """
    ids = [str(t) for t in trip_ids]
    if shuffle:
        rng = random.Random(seed)
        rng.shuffle(ids)

    n = len(ids)
    warned = False

    if n == 0:
        return SplitResult(warned=True)

    t_ratio, v_ratio, _ = ratios
    n_train = round(n * t_ratio)
    n_val = round(n * v_ratio)
    # test gets the remainder to avoid rounding drift
    n_test = n - n_train - n_val

    if n_test <= 0 or n_val <= 0 or n_train <= 0:
        warned = True

    train = ids[:n_train]
    validation = ids[n_train : n_train + n_val]
    test = ids[n_train + n_val :]

    # Trim to guaranteed minimums only if we have enough room.
    if warned:
        # Cannot honour min_trips_per_split when n is small; leave as-is.
        pass
    elif (
        min_trips_per_split > 1
        and n >= min_trips_per_split * 3
        and (len(test) < min_trips_per_split or len(validation) < min_trips_per_split)
    ):
        # Rebalance so each split has at least min_trips_per_split.
        test = ids[-min_trips_per_split:]
        remainder = ids[:-min_trips_per_split]
        val = remainder[-min_trips_per_split:]
        train = remainder[:-min_trips_per_split]
        validation = val
        warned = False

    assignment = {}
    for t in train:
        assignment[t] = "train"
    for t in validation:
        assignment[t] = "validation"
    for t in test:
        assignment[t] = "test"

    if len(assignment) < len(ids):
        warned = True

    return SplitResult(
        assignment=assignment,
        train=train,
        validation=validation,
        test=test,
        warned=warned,
    )


def remove_leakage_duplicates(trip_ids: Sequence[str]) -> List[str]:
    """Return trips with no duplicated route (same id appearing once).

    Prevents the same route appearing in multiple splits. IO-VNBD has the same
    trip id present in both synchronised and unsynchronised folders with
    different recordings; callers should de-duplicate explicitly.
    """
    seen = set()
    out = []
    for t in trip_ids:
        k = str(t).lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(str(t))
    return out