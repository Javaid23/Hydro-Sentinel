"""
Neural benchmark architectures.

LSTMRegressor       sequence of the last `window` satellite feature vectors at a site → target.
                    Real temporal context (unlike a timestep-1 pseudo-sequence), so it can only be
                    trained/evaluated at sites with ≥30 chronologically ordered observations.
FTTransformer       Feature-Tokenizer Transformer (Gorishniy et al. 2021): each numeric feature is
                    embedded as a token (x·w + b), a [CLS] token is prepended, L transformer encoder
                    layers attend across features, and the [CLS] output is regressed.

Both output the target in log1p space; callers expm1 the result.
"""

from __future__ import annotations

import torch
from torch import nn


class LSTMRegressor(nn.Module):
    def __init__(self, n_features: int, hidden: int = 48, layers: int = 1, dropout: float = 0.2):
        super().__init__()
        self.inp = nn.Linear(n_features, hidden)
        self.lstm = nn.LSTM(hidden, hidden, num_layers=layers, batch_first=True,
                            dropout=dropout if layers > 1 else 0.0)
        self.head = nn.Sequential(nn.LayerNorm(hidden), nn.Dropout(dropout), nn.Linear(hidden, hidden // 2),
                                  nn.GELU(), nn.Linear(hidden // 2, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:      # x: [batch, window, n_features]
        h, _ = self.lstm(torch.relu(self.inp(x)))
        return self.head(h[:, -1]).squeeze(-1)                 # last step = the observation being scored


class FTTransformer(nn.Module):
    def __init__(self, n_features: int, d_token: int = 48, n_layers: int = 2, n_heads: int = 4,
                 dropout: float = 0.15):
        super().__init__()
        self.w = nn.Parameter(torch.empty(n_features, d_token))
        self.b = nn.Parameter(torch.zeros(n_features, d_token))
        nn.init.kaiming_uniform_(self.w, a=5 ** 0.5)
        self.cls = nn.Parameter(torch.zeros(1, 1, d_token))
        layer = nn.TransformerEncoderLayer(d_model=d_token, nhead=n_heads, dim_feedforward=d_token * 2,
                                           dropout=dropout, activation="gelu", batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(layer, num_layers=n_layers)
        self.head = nn.Sequential(nn.LayerNorm(d_token), nn.Linear(d_token, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:      # x: [batch, n_features]
        tok = x.unsqueeze(-1) * self.w + self.b                 # [batch, n_features, d_token]
        tok = torch.cat([self.cls.expand(len(x), -1, -1), tok], dim=1)
        return self.head(self.encoder(tok)[:, 0]).squeeze(-1)
