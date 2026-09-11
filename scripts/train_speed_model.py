"""CLI to train a smartphone speed-estimation model (lstm | gru | tcn).

Thin wrapper around the shared training pipeline:
    python scripts/train_speed_model.py --model gru --epochs 10
    python scripts/train_speed_model.py                # LSTM (default)
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.models.speed_estimator.train import main as train_main


def main():
    parser = argparse.ArgumentParser(
        description="Train a smartphone speed-estimation model."
    )
    parser.add_argument(
        "--model",
        choices=["lstm", "gru", "tcn"],
        default="lstm",
        help="Architecture to train (default: lstm).",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=None,
        help="Maximum number of training epochs.",
    )
    args = parser.parse_args()

    import sys

    sys.argv = [
        "train_speed_model.py",
        "--model",
        args.model,
    ]
    if args.epochs is not None:
        sys.argv += ["--epochs", str(args.epochs)]

    train_main()


if __name__ == "__main__":
    main()