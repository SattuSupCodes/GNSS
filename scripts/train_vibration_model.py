"""CLI to train the D-T3 vibration classifier.

Thin wrapper around the shared training pipeline:
    python scripts/train_vibration_model.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.models.vibration_classifier.train import train


def main():
    train()


if __name__ == "__main__":
    main()