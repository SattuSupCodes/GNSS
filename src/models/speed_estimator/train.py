"""Production training pipeline for smartphone speed estimation.

Supports three comparable architectures for the same task:

* ``lstm`` (default) - ``SpeedLSTM``
* ``gru``             - ``SpeedGRU``
* ``tcn``             - ``SpeedTCN``

Each model writes its own checkpoint/scaler/metrics so no artifact is
overwritten. ``python src/models/speed_estimator/train.py`` still trains the
LSTM exactly as before.
"""

from pathlib import Path
import argparse
import json
import random

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from src.models.speed_estimator.dataset import SpeedSequenceDataset
from src.models.speed_estimator.features import FeatureScaler
from src.models.speed_estimator.lstm import SpeedLSTM
from src.models.speed_estimator.gru import SpeedGRU
from src.models.speed_estimator.tcn import SpeedTCN


# ============================================================
# Configuration
# ============================================================

SEED = 42

BATCH_SIZE = 32
EPOCHS = 10
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-5

PATIENCE = 3
GRADIENT_CLIP_NORM = 1.0

TRAIN_PATH = Path("data/training/sequences.parquet")
VALIDATION_PATH = Path("data/validation/sequences.parquet")
TEST_PATH = Path("data/testing/sequences.parquet")

MODEL_DIR = Path("models")

# Registry of supported architectures -> (model class, artifact stem).
MODEL_REGISTRY = {
    "lstm": SpeedLSTM,
    "gru": SpeedGRU,
    "tcn": SpeedTCN,
}


def artifact_paths(model_type: str) -> tuple:
    """Return (checkpoint, scaler, metrics) paths for a model type."""
    stem = f"speed_{model_type}"
    return (
        MODEL_DIR / f"{stem}.pt",
        MODEL_DIR / f"{stem}_scaler.npz",
        MODEL_DIR / f"{stem}_metrics.json",
    )


def build_model(model_type: str, checkpoint: dict = None):
    """Instantiate the requested architecture.

    Without a checkpoint the defaults used by the original LSTM training are
    chosen; with a checkpoint the stored hyper-parameters win so a model can
    be reloaded exactly.
    """
    model_class = MODEL_REGISTRY[model_type]

    if checkpoint is None:
        checkpoint = {}

    if model_type in ("lstm", "gru"):
        return model_class(
            input_size=checkpoint.get("input_size", 9),
            hidden_size=checkpoint.get("hidden_size", 64),
            num_layers=checkpoint.get("num_layers", 2),
        )

    if model_type == "tcn":
        return model_class(
            input_size=checkpoint.get("input_size", 9),
            channels=checkpoint.get("channels", 32),
            dilations=tuple(checkpoint.get("dilations", [1, 2, 4, 8])),
        )

    raise ValueError(f"Unknown model type: {model_type}")


# ============================================================
# Reproducibility
# ============================================================

def set_seed(seed: int = SEED):
    """Make training as reproducible as practical."""

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ============================================================
# Dataset loading
# ============================================================

def load_dataset(path: Path):
    """Load sequence dataset into NumPy arrays."""

    print(f"Loading: {path}")

    dataset = SpeedSequenceDataset(str(path))

    if len(dataset) == 0:
        raise RuntimeError(f"No valid sequences found in {path}")

    x = np.stack([
        item[0].numpy()
        for item in dataset
    ])

    y = np.stack([
        item[1].numpy()
        for item in dataset
    ])

    mask = np.stack([
        item[2].numpy()
        for item in dataset
    ])

    return x, y, mask


def make_loader(
    x: np.ndarray,
    y: np.ndarray,
    mask: np.ndarray,
    shuffle: bool,
):
    """Create a PyTorch DataLoader."""

    dataset = TensorDataset(
        torch.from_numpy(x).float(),
        torch.from_numpy(y).float(),
        torch.from_numpy(mask).bool(),
    )

    return DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=shuffle,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )


# ============================================================
# Loss
# ============================================================

def masked_mse_loss(
    prediction: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
):
    """MSE loss that ignores invalid target samples."""

    valid_prediction = prediction[mask]
    valid_target = target[mask]

    if valid_target.numel() == 0:
        return None

    return torch.mean(
        (valid_prediction - valid_target) ** 2
    )


# ============================================================
# Metrics
# ============================================================

def calculate_metrics(
    prediction: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
):
    """Calculate MSE, RMSE and MAE."""

    prediction = prediction[mask]
    target = target[mask]

    if target.numel() == 0:
        return {
            "mse": float("nan"),
            "rmse": float("nan"),
            "mae": float("nan"),
            "samples": 0,
        }

    errors = prediction - target

    mse = torch.mean(errors ** 2).item()
    rmse = float(np.sqrt(mse))
    mae = torch.mean(torch.abs(errors)).item()

    return {
        "mse": mse,
        "rmse": rmse,
        "mae": mae,
        "samples": int(target.numel()),
    }


# ============================================================
# Training
# ============================================================

def train_one_epoch(
    model,
    loader,
    optimizer,
    device,
):
    """Run one training epoch."""

    model.train()

    total_loss = 0.0
    total_samples = 0

    for x, y, mask in loader:

        x = x.to(device)
        y = y.to(device)
        mask = mask.to(device)

        prediction = model(x)

        loss = masked_mse_loss(
            prediction,
            y,
            mask,
        )

        if loss is None:
            continue

        optimizer.zero_grad()

        loss.backward()

        # Prevent unstable gradient explosions.
        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            GRADIENT_CLIP_NORM,
        )

        optimizer.step()

        valid_samples = int(mask.sum().item())

        total_loss += loss.item() * valid_samples
        total_samples += valid_samples

    if total_samples == 0:
        raise RuntimeError(
            "Training produced zero valid target samples."
        )

    return total_loss / total_samples


# ============================================================
# Validation / evaluation
# ============================================================

def evaluate(
    model,
    loader,
    device,
):
    """Evaluate model without updating weights."""

    model.eval()

    all_predictions = []
    all_targets = []
    all_masks = []

    with torch.no_grad():

        for x, y, mask in loader:

            x = x.to(device)
            y = y.to(device)
            mask = mask.to(device)

            prediction = model(x)

            all_predictions.append(
                prediction.cpu()
            )

            all_targets.append(
                y.cpu()
            )

            all_masks.append(
                mask.cpu()
            )

    predictions = torch.cat(all_predictions)
    targets = torch.cat(all_targets)
    masks = torch.cat(all_masks)

    metrics = calculate_metrics(
        predictions,
        targets,
        masks,
    )

    return metrics


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Train a smartphone speed-estimation model."
    )
    parser.add_argument(
        "--model",
        choices=list(MODEL_REGISTRY),
        default="lstm",
        help="Architecture to train (default: lstm).",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=EPOCHS,
        help="Maximum number of training epochs.",
    )
    args = parser.parse_args()

    model_type = args.model
    epochs = args.epochs
    model_class = MODEL_REGISTRY[model_type]

    MODEL_PATH, SCALER_PATH, METRICS_PATH = artifact_paths(model_type)

    set_seed()

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print()
    print("=" * 60)
    print(
        f"SMARTPHONE SPEED ESTIMATION - {model_type.upper()} TRAINING"
    )
    print("=" * 60)
    print(f"Device: {device}")
    print(f"Seed: {SEED}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Epochs: {epochs}")
    print(f"Learning rate: {LEARNING_RATE}")
    print()

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    train_x, train_y, train_mask = load_dataset(
        TRAIN_PATH
    )

    validation_x, validation_y, validation_mask = load_dataset(
        VALIDATION_PATH
    )

    test_x, test_y, test_mask = load_dataset(
        TEST_PATH
    )

    print()
    print("Dataset shapes:")
    print("  Train:      ", train_x.shape)
    print("  Validation: ", validation_x.shape)
    print("  Test:       ", test_x.shape)

    # --------------------------------------------------------
    # Feature scaling
    # --------------------------------------------------------

    scaler = FeatureScaler()

    train_x = scaler.fit_transform(train_x)

    validation_x = scaler.transform(
        validation_x
    )

    test_x = scaler.transform(
        test_x
    )

    print()
    print("Feature scaling complete.")

    # Save scaler statistics.
    np.savez(
        SCALER_PATH,
        mean=scaler.mean,
        std=scaler.std,
    )

    print(
        f"Scaler saved → {SCALER_PATH}"
    )

    # --------------------------------------------------------
    # DataLoaders
    # --------------------------------------------------------

    train_loader = make_loader(
        train_x,
        train_y,
        train_mask,
        shuffle=True,
    )

    validation_loader = make_loader(
        validation_x,
        validation_y,
        validation_mask,
        shuffle=False,
    )

    test_loader = make_loader(
        test_x,
        test_y,
        test_mask,
        shuffle=False,
    )

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    model = build_model(model_type)

    model = model.to(device)

    print()
    print(model)

    parameter_count = sum(
        parameter.numel()
        for parameter in model.parameters()
        if parameter.requires_grad
    )

    print(
        f"Trainable parameters: {parameter_count:,}"
    )

    # --------------------------------------------------------
    # Optimizer and scheduler
    # --------------------------------------------------------

    loss_function = nn.MSELoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=0.5,
        patience=1,
    )

    # --------------------------------------------------------
    # Training loop
    # --------------------------------------------------------

    best_validation_rmse = float("inf")
    epochs_without_improvement = 0

    history = []

    print()
    print("=" * 60)
    print("TRAINING")
    print("=" * 60)

    for epoch in range(1, epochs + 1):

        train_loss = train_one_epoch(
            model,
            train_loader,
            optimizer,
            device,
        )

        validation_metrics = evaluate(
            model,
            validation_loader,
            device,
        )

        validation_rmse = validation_metrics["rmse"]

        scheduler.step(validation_rmse)

        current_lr = optimizer.param_groups[0]["lr"]

        print(
            f"Epoch {epoch:02d}/{epochs} "
            f"| Train MSE: {train_loss:.4f} "
            f"| Val RMSE: {validation_metrics['rmse']:.4f} km/h "
            f"| Val MAE: {validation_metrics['mae']:.4f} km/h "
            f"| LR: {current_lr:.6f}"
        )

        history.append({
            "epoch": epoch,
            "train_mse": train_loss,
            "validation_mse": validation_metrics["mse"],
            "validation_rmse": validation_metrics["rmse"],
            "validation_mae": validation_metrics["mae"],
            "learning_rate": current_lr,
        })

        # ----------------------------------------------------
        # Save best model
        # ----------------------------------------------------

        if validation_rmse < best_validation_rmse:

            best_validation_rmse = validation_rmse
            epochs_without_improvement = 0

            if model_type in ("lstm", "gru"):
                arch_params = {
                    "input_size": 9,
                    "hidden_size": 64,
                    "num_layers": 2,
                }
            else:
                arch_params = {
                    "input_size": 9,
                    "channels": 32,
                    "dilations": [1, 2, 4, 8],
                }

            checkpoint = {
                "model_type": model_type,
                "model_state_dict": model.state_dict(),
                **arch_params,
                "feature_columns": [
                    "accel_x_cal",
                    "accel_y_cal",
                    "accel_z_cal",
                    "gyro_x_cal",
                    "gyro_y_cal",
                    "gyro_z_cal",
                    "mag_x_cal",
                    "mag_y_cal",
                    "mag_z_cal",
                ],
                "target_column": "speed_kmh",
                "best_validation_rmse": best_validation_rmse,
            }

            torch.save(
                checkpoint,
                MODEL_PATH,
            )

            print(
                f"  ✓ Best model saved → {MODEL_PATH}"
            )

        else:

            epochs_without_improvement += 1

            if epochs_without_improvement >= PATIENCE:

                print()
                print(
                    "Early stopping: validation "
                    "performance stopped improving."
                )

                break

    # --------------------------------------------------------
    # Load best model
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("FINAL TEST EVALUATION")
    print("=" * 60)

    checkpoint = torch.load(
        MODEL_PATH,
        map_location=device,
    )

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    test_metrics = evaluate(
        model,
        test_loader,
        device,
    )

    print(
        f"Test MSE:  {test_metrics['mse']:.4f}"
    )

    print(
        f"Test RMSE: {test_metrics['rmse']:.4f} km/h"
    )

    print(
        f"Test MAE:  {test_metrics['mae']:.4f} km/h"
    )

    print(
        f"Valid samples: {test_metrics['samples']:,}"
    )

    # --------------------------------------------------------
    # Save metrics
    # --------------------------------------------------------

    results = {
        "model": f"Speed{model_type.upper()}",
        "model_type": model_type,
        "device": str(device),
        "seed": SEED,
        "batch_size": BATCH_SIZE,
        "epochs_requested": epochs,
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "input_size": 9,
        "sequence_length": 100,
        "best_validation_rmse": best_validation_rmse,
        "test_metrics": test_metrics,
        "history": history,
    }

    with open(
        METRICS_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            results,
            file,
            indent=2,
        )

    print()
    print(
        f"Metrics saved → {METRICS_PATH}"
    )

    print()
    print("=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()