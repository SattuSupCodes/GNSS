"""Lightweight Temporal Convolutional Network for speed estimation.

Causal dilated convolutions only ever look at past samples, so no future
information leaks into a per-timestep prediction. Kept small on purpose so it
trains fast on CPU and stays comparable with the LSTM/GRU.
"""

import torch
import torch.nn as nn


class CausalConv1dBlock(nn.Module):
    """One causal dilated 1D convolution + ReLU (+ optional dropout)."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        dilation: int,
        dropout: float = 0.0,
    ):
        super().__init__()

        # Padding = dilation * (kernel - 1) keeps the output aligned with the
        # last input sample. The right-side padding is cropped afterwards so
        # the block only ever looks at past samples (causal).
        self.conv = nn.Conv1d(
            in_channels,
            out_channels,
            kernel_size=3,
            padding=dilation * (3 - 1),
            dilation=dilation,
            bias=True,
        )

        self.activation = nn.ReLU()

        self.dropout = (
            nn.Dropout(dropout)
            if dropout > 0.0
            else nn.Identity()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv(x)

        # Trim the right-side causal padding produced by Conv1d.
        out = out[:, :, : x.size(2)]

        return self.dropout(self.activation(out))


class SpeedTCN(nn.Module):
    """Per-timestep speed predictor built from stacked causal dilated blocks."""

    def __init__(
        self,
        input_size: int = 9,
        channels: int = 32,
        dilations=(1, 2, 4, 8),
        dropout: float = 0.1,
    ):
        super().__init__()

        self.input_projection = nn.Conv1d(
            input_size,
            channels,
            kernel_size=1,
        )

        blocks = []

        for dilation in dilations:
            blocks.append(
                CausalConv1dBlock(
                    channels,
                    channels,
                    dilation=dilation,
                    dropout=dropout,
                )
            )

        self.blocks = nn.Sequential(*blocks)

        self.output_projection = nn.Conv1d(
            channels,
            1,
            kernel_size=1,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return per-timestep speed predictions with shape (batch, seq_len)."""

        # (batch, seq_len, channels) -> (batch, channels, seq_len)
        x = x.transpose(1, 2)

        x = self.input_projection(x)
        x = self.blocks(x)

        speed = self.output_projection(x)

        # (batch, 1, seq_len) -> (batch, seq_len)
        speed = speed.squeeze(1)

        return speed