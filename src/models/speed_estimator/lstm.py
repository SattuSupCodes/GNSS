"""LSTM model for smartphone speed estimation."""

import torch
import torch.nn as nn

class SpeedLSTM(nn.Module):
    def __init__(
            self,
            input_size: int = 9,
            hidden_size: int = 64,
            num_layers: int = 2,
    ):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size= input_size,
            hidden_size= hidden_size,
            num_layers= num_layers,
            batch_first= True,
        )

        self.output_layer = nn.Linear(hidden_size, 1)

    def forward(self, x):
        lstm_output, _ = self.lstm(x)

        speed = self.output_layer(lstm_output)

        speed = speed.squeeze(-1)

        return speed