"""GRU model for smartphone speed estimation.

Mirrors the LSTM's interface and capacity (input_size=9, hidden=64, layers=2,
per-timestep output) so LSTM/GRU/TCN comparisons are meaningful.
"""

import torch
import torch.nn as nn


class SpeedGRU(nn.Module):
    """Bidirectional-free GRU that predicts a speed for every timestep."""

    def __init__(
        self,
        input_size: int = 9,
        hidden_size: int = 64,
        num_layers: int = 2,
    ):
        super().__init__()

        self.gru = nn.GRU(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )

        self.output_layer = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return per-timestep speed predictions with shape (batch, seq_len)."""
        gru_output, _ = self.gru(x)

        speed = self.output_layer(gru_output)

        speed = speed.squeeze(-1)

        return speed