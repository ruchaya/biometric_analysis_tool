# -*- coding: utf-8 -*-
"""Residual, Q-Q and Cook's D diagnostics for allometric log-log fits."""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from repro_common import BASE, load_data

FIGDIR = os.path.join(BASE, "figures")
os.makedirs(FIGDIR, exist_ok=True)

df = load_data()
fits = {
    "Chuvash males": (df["group"] == "Chuvash") & (df["sex"] == "Male"),
    "Chuvash females": (df["group"] == "Chuvash") & (df["sex"] == "Female"),
    "Anish males": (df["group"] == "Anish") & (df["sex"] == "Male"),
    "Anish females": (df["group"] == "Anish") & (df["sex"] == "Female"),
    "Pooled males": df["sex"] == "Male",
    "Pooled females": df["sex"] == "Female",
}

res = {}
cooks = []
for name, mask in fits.items():
    sub = df[mask].copy()
    x = np.log(sub["Length"].values.astype(float))
    y = np.log(sub["Weight"].values.astype(float))
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ beta
    resid = y - fitted
    n, p = X.shape
    mse = np.sum(resid ** 2) / (n - p)
    H = X @ np.linalg.inv(X.T @ X) @ X.T
    h = np.diag(H)
    cook = (resid ** 2) / (p * mse) * h / (1 - h) ** 2
    imax = int(np.argmax(cook))
    cooks.append({
        "Fit": name, "n": int(n), "Max_Cooks_D": float(cook[imax]),
        "Threshold_4_over_n": float(4 / n), "N_above_threshold": int((cook > 4 / n).sum()),
        "Fish_ID": int(sub["№"].iloc[imax]), "Weight_g": float(sub["Вес, г"].iloc[imax]),
        "TL_cm": float(sub["Длина, см"].iloc[imax]),
    })
    res[name] = (fitted, resid)

pd.DataFrame(cooks).to_csv(os.path.join(BASE, "cooks_d.csv"), index=False)

fig, axes = plt.subplots(3, 2, figsize=(12, 13))
axes = axes.flatten()
for ax, (name, (fitted, resid)) in zip(axes, res.items()):
    ax.scatter(fitted, resid, alpha=0.7, color="#4C72B0")
    ax.axhline(0, color="red", linestyle="--", linewidth=1.5)
    ax.set_title(name)
    ax.set_xlabel("Fitted log weight")
    ax.set_ylabel("Residual")
    ax.grid(True, alpha=0.3)
plt.tight_layout()
fig.savefig(os.path.join(FIGDIR, "Supplementary_Figure_S1a.png"), dpi=150)
plt.close(fig)

fig, axes = plt.subplots(3, 2, figsize=(12, 13))
axes = axes.flatten()
for ax, (name, (fitted, resid)) in zip(axes, res.items()):
    stats.probplot(resid, dist="norm", plot=ax)
    ax.set_title(name)
    ax.set_xlabel("Theoretical quantiles")
    ax.set_ylabel("Ordered values")
    ax.grid(True, alpha=0.3)
plt.tight_layout()
fig.savefig(os.path.join(FIGDIR, "Supplementary_Figure_S1b.png"), dpi=150)
plt.close(fig)
print("written cooks_d.csv and Supplementary_Figure_S1a/S1b")
