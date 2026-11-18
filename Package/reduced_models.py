# -*- coding: utf-8 -*-
"""Full, Reduced A and Reduced B linear models with repeated cross-validation."""
import os
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import RepeatedKFold
from repro_common import (
    BASE, load_data, make_pipeline, metrics,
    FULL_NUM, REDUCED_A_NUM, REDUCED_B_NUM, CAT,
)

df = load_data()
tr = df["Split"] == "Train"
te = df["Split"] == "Test"
y = df["Weight"]
rkf = RepeatedKFold(n_splits=5, n_repeats=5, random_state=42)


def vif_table(X, cols):
    out = {}
    for c in cols:
        others = [x for x in cols if x != c]
        lr = LinearRegression().fit(X[others], X[c])
        r2 = lr.score(X[others], X[c])
        out[c] = float(1 / (1 - r2)) if r2 < 1 else float("inf")
    return out


def evaluate(name, num, categorical):
    cols = num + (CAT if categorical else [])
    X = df[cols]
    pipe = make_pipeline(num, categorical)
    pipe.fit(X[tr], y[tr])
    m = metrics(y[te], pipe.predict(X[te]))
    vals = {"MAE": [], "RMSE": [], "R2": []}
    for a, b in rkf.split(X):
        p = make_pipeline(num, categorical)
        p.fit(X.iloc[a], y.iloc[a])
        yp = p.predict(X.iloc[b])
        mm = metrics(y.iloc[b], yp)
        for k in vals:
            vals[k].append(mm[k])
    rep = {k: (float(np.mean(v)), float(np.std(v, ddof=1))) for k, v in vals.items()}
    vif = vif_table(X, num)
    return {
        "Model": name, "n_predictors": len(num) + (2 if categorical else 0),
        "Test_MAE": m["MAE"], "Test_RMSE": m["RMSE"], "Test_R2": m["R2"],
        "RepeatedCV_MAE_mean": rep["MAE"][0], "RepeatedCV_MAE_SD": rep["MAE"][1],
        "Max_VIF": max(vif.values()),
    }


rows = [
    evaluate("Full (8 numeric + 2 categorical)", FULL_NUM, True),
    evaluate("Reduced A (TL, GC, H, age, group, sex)", REDUCED_A_NUM, True),
    evaluate("Reduced B (TL, GC, H)", REDUCED_B_NUM, False),
]
pd.DataFrame(rows).to_csv(os.path.join(BASE, "reduced_models.csv"), index=False)
print("written reduced_models.csv")
