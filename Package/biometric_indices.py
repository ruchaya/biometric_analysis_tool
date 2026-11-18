# -*- coding: utf-8 -*-
"""Group-by-sex biometric indices (Supplementary Table S2)."""
import os
import numpy as np
import pandas as pd
from repro_common import BASE, load_data

df = load_data()
df["K"] = 100 * df["Weight"] / df["Commercial_Length"] ** 3
df["PDI"] = df["Weight"] * df["Commercial_Length"] / 100
df["RW"] = 1000 * df["Weight"] / df["Commercial_Length"]
df["LHI"] = 100 * df["HL"] / df["Commercial_Length"]
df["RI"] = 100 * df["Commercial_Length"] / df["Max_Height"]
GROUP_FULL = {"Parsky": "Parsky Moscow scattered type", "Czech": "Czech scaled carp", "Chuvash": "Chuvash scaled carp", "Petrovsky": "Petrovsky carp cross", "Anish": "Anish mirror carp"}
df["group_full"] = df["group"].map(GROUP_FULL)

rows = []
for (group, sex), sub in df.groupby(["group_full", "sex"]):
    row = {"Breeding_group": group, "Sex": sex, "n": len(sub)}
    for col in ["K", "PDI", "RW", "LHI", "RI"]:
        mean = sub[col].mean()
        se = sub[col].std(ddof=1) / np.sqrt(len(sub)) if len(sub) > 1 else np.nan
        row[col] = f"{mean:.2f} ± {se:.2f}" if len(sub) > 1 else f"{mean:.2f}"
    rows.append(row)
pd.DataFrame(rows).to_csv(os.path.join(BASE, "biometric_indices.csv"), index=False)
print("written biometric_indices.csv")
