"""
Shared pieces for the neural benchmarks: standardisation, windowing, a generic trainer.

Everything is fit on the training portion only. Sequence windows never cross a site boundary,
and a window only looks backwards in time, so the split designs of evaluation.py stay
leakage-safe.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np
import pandas as pd

from hydrosentinel import config as C

# torch is imported lazily inside the functions that need it, so the windowing helpers
# (pure numpy) stay importable and testable in environments without torch.

MIN_SITE_OBS_SEQ = 30      # spec: LSTM only for sites with ≥30 chronologically ordered observations


def set_seed(seed: int = C.RANDOM_STATE) -> None:
    import torch
    np.random.seed(seed)
    torch.manual_seed(seed)


@dataclass
class Scaler:
    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, X: np.ndarray) -> "Scaler":
        return cls(mean=X.mean(axis=0), std=X.std(axis=0) + 1e-9)

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean) / self.std


def build_windows(df: pd.DataFrame, X: np.ndarray, window: int, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each row in `idx`, a window of the last `window` feature vectors at the same site
    (chronological, ending at the row itself), left-padded by repeating the earliest row.

    Returns (seq [n, window, d], mask [n, window] 1=real 0=pad, kept_idx). Only sites with
    ≥ MIN_SITE_OBS_SEQ rows *within idx* are kept (spec rule), so eligibility is decided per split.
    """
    sub = df.iloc[idx]
    order = np.argsort(sub["scene_datetime_utc"].to_numpy(), kind="stable")
    idx_sorted = idx[order]
    site = df["site_no"].to_numpy()[idx_sorted]
    seqs, masks, kept = [], [], []
    for s in pd.unique(site):
        rows = idx_sorted[site == s]
        if len(rows) < MIN_SITE_OBS_SEQ:
            continue
        for j, r in enumerate(rows):
            lo = max(0, j - window + 1)
            w = rows[lo:j + 1]
            pad = window - len(w)
            seq = np.vstack([np.repeat(X[w[:1]], pad, axis=0), X[w]]) if pad else X[w]
            mask = np.concatenate([np.zeros(pad), np.ones(len(w))])
            seqs.append(seq); masks.append(mask); kept.append(r)
    if not seqs:
        return np.empty((0, window, X.shape[1])), np.empty((0, window)), np.array([], dtype=int)
    return np.stack(seqs).astype(np.float32), np.stack(masks).astype(np.float32), np.array(kept)


def train_model(model, X_tr, y_tr, X_val, y_val, *, epochs: int = 300, lr: float = 1e-3,
                batch_size: int = 64, patience: int = 25, weight_decay: float = 1e-4):
    """Generic MSE trainer with AdamW + early stopping on validation loss. Inputs are tensors/arrays
    already in model space (standardised features, log1p targets). Returns (model, best_epoch)."""
    import torch
    from torch import nn
    X_tr, y_tr = torch.as_tensor(X_tr), torch.as_tensor(y_tr, dtype=torch.float32)
    X_val, y_val = torch.as_tensor(X_val), torch.as_tensor(y_val, dtype=torch.float32)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=10)
    loss_fn = nn.MSELoss()
    best, best_state, best_epoch, bad = float("inf"), copy.deepcopy(model.state_dict()), 0, 0
    n = len(X_tr)
    for epoch in range(1, epochs + 1):
        model.train()
        perm = torch.randperm(n)
        for i in range(0, n, batch_size):
            b = perm[i:i + batch_size]
            opt.zero_grad()
            loss = loss_fn(model(X_tr[b]), y_tr[b])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            vl = loss_fn(model(X_val), y_val).item()
        sched.step(vl)
        if vl < best - 1e-5:
            best, best_state, best_epoch, bad = vl, copy.deepcopy(model.state_dict()), epoch, 0
        else:
            bad += 1
            if bad >= patience:
                break
    model.load_state_dict(best_state)
    model.eval()
    return model, best_epoch


def predict(model, X, batch_size: int = 512) -> np.ndarray:
    import torch
    model.eval()
    X = torch.as_tensor(X)
    with torch.no_grad():
        out = [model(X[i:i + batch_size]).cpu().numpy() for i in range(0, len(X), batch_size)]
    return np.concatenate(out) if out else np.array([])
