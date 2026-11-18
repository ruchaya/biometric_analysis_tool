# -*- coding: utf-8 -*-
"""Out-of-fold permutation importance for the final linear model."""
import os
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.inspection import permutation_importance
from repro_common import BASE, load_data, make_pipeline, FULL_NUM, CAT

df = load_data()
tr = df["Split"] == "Train"
X = df[FULL_NUM + CAT]
y = df["Weight"]
Xtr, ytr = X[tr], y[tr]

kf = KFold(n_splits=5, shuffle=True, random_state=42)
imp = {c: [] for c in Xtr.columns}
for a, b in kf.split(Xtr):
    pipe = make_pipeline(FULL_NUM, categorical=True)
    pipe.fit(Xtr.iloc[a], ytr.iloc[a])
    res = permutation_importance(
        pipe, Xtr.iloc[b], ytr.iloc[b],
        n_repeats=200, random_state=42, scoring="r2", n_jobs=-1,
    )
    for i, c in enumerate(Xtr.columns):
        imp[c].append(float(res.importances_mean[i]))

rows = []
for c, vals in imp.items():
    rows.append({"Feature": c, "Mean_delta_R2": float(np.mean(vals)), "SD_delta_R2": float(np.std(vals, ddof=1))})
pd.DataFrame(rows).to_csv(os.path.join(BASE, "permutation_importance_oof.csv"), index=False)
print("written permutation_importance_oof.csv")
