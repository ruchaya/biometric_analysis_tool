# -*- coding: utf-8 -*-
"""Sensitivity analyses: 7,250 g observation and rare breeding groups."""
import os
import pandas as pd
from repro_common import BASE, load_data, make_pipeline, metrics, FULL_NUM, CAT

df = load_data()
tr = df["Split"] == "Train"
te = df["Split"] == "Test"
y = df["Weight"]
X = df[FULL_NUM + CAT]


def fit_eval(train_mask, test_mask):
    pipe = make_pipeline(FULL_NUM, categorical=True)
    pipe.fit(X[train_mask], y[train_mask])
    return metrics(y[test_mask], pipe.predict(X[test_mask]))


# 7,250 g sensitivity (fish ID 1)
mask_7250 = df["№"] == 1
rows = [
    {"Analysis": "Full training set", "Train_n": int(tr.sum()), "Test_n": int(te.sum()), **fit_eval(tr, te)},
    {"Analysis": "Excluding 7250 g fish from training", "Train_n": int((tr & ~mask_7250).sum()),
     "Test_n": int(te.sum()), **fit_eval(tr & ~mask_7250, te)},
]
pd.DataFrame(rows).to_csv(os.path.join(BASE, "sensitivity_7250.csv"), index=False)

# Rare-group sensitivity
rare = df["group"].isin(["Parsky", "Czech", "Petrovsky"])
tr_core = tr & ~rare
te_core = te & ~rare
rows = [
    {"Analysis": "Full model, all 44 test fish", "Train_n": int(tr.sum()), "Test_n": int(te.sum()),
     **fit_eval(tr, te)},
    {"Analysis": "Full model, Chuvash+Anish test subset", "Train_n": int(tr.sum()), "Test_n": int(te_core.sum()),
     **fit_eval(tr, te_core)},
    {"Analysis": "Model trained without rare groups, Chuvash+Anish test subset",
     "Train_n": int(tr_core.sum()), "Test_n": int(te_core.sum()), **fit_eval(tr_core, te_core)},
]
# Collapsed group model
df2 = df.copy()
df2["group"] = df2["group"].where(~df2["group"].isin(["Parsky", "Czech", "Petrovsky"]), "Other")
X2 = df2[FULL_NUM + CAT]
pipe = make_pipeline(FULL_NUM, categorical=True)
pipe.fit(X2[tr], y[tr])
m = metrics(y[te], pipe.predict(X2[te]))
rows.append({"Analysis": "Rare groups collapsed to 'Other', all 44 test fish",
             "Train_n": int(tr.sum()), "Test_n": int(te.sum()), **m})
pd.DataFrame(rows).to_csv(os.path.join(BASE, "sensitivity_rare_groups.csv"), index=False)
print("written sensitivity_7250.csv and sensitivity_rare_groups.csv")
