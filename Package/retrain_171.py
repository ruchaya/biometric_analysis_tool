# -*- coding: utf-8 -*-
import os, json, warnings, time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import seaborn as sns

from sklearn.model_selection import GridSearchCV, RepeatedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression, LassoCV
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor, ExtraTreesRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import wilcoxon, t as tdist

warnings.filterwarnings("ignore")

BASE = os.path.dirname(os.path.abspath(__file__))
BASE_XLSX = os.path.join(BASE, "modeling_data_215.csv")
SPLIT = os.path.join(BASE, "split.csv")
OUT = os.path.join(BASE, "retrain_171_outputs")
os.makedirs(OUT, exist_ok=True)

# ---------------- data ----------------
df = pd.read_csv(BASE_XLSX)
split = pd.read_csv(SPLIT)
df = df.merge(split[["ID", "Split"]], left_on="№", right_on="ID", how="left")
assert df["Split"].notna().all() and len(df) == 215

group_map = {
    "парский зеркальный": "Parsky Moscow scattered type",
    "чешский чешуйчатый": "Czech scaled carp",
    "чувашский чешуйчатый": "Chuvash scaled carp",
    "петровский чешуйчатый": "Petrovsky carp cross",
    "анишский зеркальный": "Anish mirror carp",
    "зеркальный анишский": "Anish mirror carp",
}
df["group"] = (df["Примечание"].astype(str).str.strip().str.lower()
               .str.replace(r"\s+", " ", regex=True).map(group_map))
df["sex"] = df["Пол"].astype(str).str.strip().str.upper().map({"Ж": "Female", "М": "Male"})
assert df["group"].notna().all() and df["sex"].notna().all()

df["Weight"] = pd.to_numeric(df["Вес, г"])
df["Length"] = pd.to_numeric(df["Длина, см"])
df["Commercial_Length"] = pd.to_numeric(df["Промыс.длина, см"])
df["Girth"] = pd.to_numeric(df["Обхват, см"])
df["Max_Height"] = pd.to_numeric(df["Наиб. Высота, см"])
df["Age"] = pd.to_numeric(df["Возраст, л (по состоянию на весну 2025)"])
df["Volume_Estimate"] = df["Length"] * df["Girth"] * df["Max_Height"]
df["Length_Girth_Ratio"] = df["Length"] / df["Girth"]
df["Cross_Section_Area"] = np.pi * (df["Girth"] / (2 * np.pi)) ** 2

numeric_features = [
    "Length", "Commercial_Length", "Girth", "Max_Height", "Age",
    "Volume_Estimate", "Length_Girth_Ratio", "Cross_Section_Area",
]
categorical_features = ["group", "sex"]
X = df[numeric_features + categorical_features].copy()
y = df["Weight"].copy()

train_mask = df["Split"] == "Train"
test_mask = df["Split"] == "Test"
X_train, y_train = X[train_mask], y[train_mask]
X_test, y_test = X[test_mask], y[test_mask]
print("train/test", X_train.shape, X_test.shape, flush=True)

preprocessor = ColumnTransformer(transformers=[
    ("num", Pipeline([("scaler", StandardScaler())]), numeric_features),
    ("cat", Pipeline([("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categorical_features),
])

models = {
    "Linear regression": LinearRegression(),
    "Decision tree": DecisionTreeRegressor(random_state=42, max_depth=5),
    "Random forest": RandomForestRegressor(random_state=42, n_estimators=100),
    "Gradient boosting": GradientBoostingRegressor(random_state=42, n_estimators=100),
    "Voting regressor": VotingRegressor(estimators=[
        ("lasso", LassoCV(random_state=42)),
        ("gradient_boosting", GradientBoostingRegressor(n_estimators=40, random_state=42)),
        ("knn", KNeighborsRegressor()),
        ("et", ExtraTreesRegressor(n_estimators=40, max_depth=3, random_state=42)),
        ("rf", RandomForestRegressor(n_estimators=40, max_depth=3, random_state=42)),
    ]),
}

param_grids = {
    "Linear regression": {"model__fit_intercept": [True, False]},
    "Decision tree": {
        "model__max_depth": [3, 5, 7, 10, 15, None],
        "model__min_samples_split": [2, 5, 10, 20],
        "model__min_samples_leaf": [1, 2, 4, 8],
        "model__max_features": ["sqrt", "log2", None],
    },
    "Random forest": {
        "model__n_estimators": [50, 100, 200, 300],
        "model__max_depth": [5, 10, 20, 30, None],
        "model__min_samples_split": [2, 5, 10],
        "model__min_samples_leaf": [1, 2, 4],
        "model__max_features": ["sqrt", "log2", 0.8],
    },
    "Gradient boosting": {
        "model__n_estimators": [50, 100, 200, 300],
        "model__learning_rate": [0.01, 0.05, 0.1, 0.2],
        "model__max_depth": [3, 5, 7, 9],
        "model__min_samples_split": [2, 5, 10],
        "model__min_samples_leaf": [1, 2, 4],
    },
    "Voting regressor": {
        "model__lasso__eps": [1e-4, 1e-3],
        "model__lasso__n_alphas": [100],
        "model__gradient_boosting__n_estimators": [50, 100],
        "model__gradient_boosting__learning_rate": [0.05, 0.1],
        "model__gradient_boosting__max_depth": [3, 5],
        "model__knn__n_neighbors": [3, 5, 7],
        "model__knn__weights": ["uniform", "distance"],
        "model__et__n_estimators": [50, 100],
        "model__et__max_depth": [5, 10],
        "model__rf__n_estimators": [50, 100],
        "model__rf__max_depth": [5, 10],
        "model__weights": [
            (0.2, 0.2, 0.2, 0.2, 0.2),
            (0.1, 0.2, 0.2, 0.25, 0.25),
            (0.2, 0.1, 0.15, 0.25, 0.3),
        ],
    },
}


def metrics(y_true, y_pred):
    err = y_true - y_pred
    rel = np.abs(err) / y_true * 100
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "R2": float(r2_score(y_true, y_pred)),
        "MRE": float(np.mean(rel)),
        "MaxErr": float(np.max(np.abs(err))),
        "Acc10": float(np.mean(rel <= 10) * 100),
        "Acc5": float(np.mean(rel <= 5) * 100),
    }


results = {}
preds = {}
fitted = {}

for name, model in models.items():
    t0 = time.time()
    pipe = Pipeline([("preprocessor", preprocessor), ("model", model)])
    pipe.fit(X_train, y_train)
    train_pred = pipe.predict(X_train)
    test_pred = pipe.predict(X_test)
    cv = cross_val_score(pipe, X_train, y_train, cv=5, scoring="r2")
    results[name] = {
        "model": name,
        "status": "Default",
        **{f"train_{k}": v for k, v in metrics(y_train, train_pred).items()},
        **{f"test_{k}": v for k, v in metrics(y_test, test_pred).items()},
        "cv_mean": float(np.mean(cv)),
        "cv_std": float(np.std(cv)),
    }
    preds[name] = {"train": train_pred, "test": test_pred}
    fitted[name] = pipe
    print("DEFAULT", name, results[name]["test_MAE"], f"{time.time()-t0:.1f}s", flush=True)

    # tuned
    t0 = time.time()
    gs = GridSearchCV(
        estimator=Pipeline([("preprocessor", preprocessor), ("model", model)]),
        param_grid=param_grids[name],
        cv=3,
        scoring="r2",
        n_jobs=-1,
        verbose=0,
    )
    gs.fit(X_train, y_train)
    best = gs.best_estimator_
    train_pred_t = best.predict(X_train)
    test_pred_t = best.predict(X_test)
    idx = int(np.where(gs.cv_results_["rank_test_score"] == 1)[0][0])
    tuned_name = name + ", tuned"
    results[tuned_name] = {
        "model": tuned_name,
        "status": "Tuned",
        **{f"train_{k}": v for k, v in metrics(y_train, train_pred_t).items()},
        **{f"test_{k}": v for k, v in metrics(y_test, test_pred_t).items()},
        "cv_mean": float(gs.best_score_),
        "cv_std": float(gs.cv_results_["std_test_score"][idx]),
        "best_params": {k: str(v) for k, v in gs.best_params_.items()},
    }
    preds[tuned_name] = {"train": train_pred_t, "test": test_pred_t}
    fitted[tuned_name] = best
    print("TUNED", tuned_name, results[tuned_name]["test_MAE"], f"{time.time()-t0:.1f}s", flush=True)
    print("PARAMS", gs.best_params_, flush=True)

# ---------------- bootstrap CIs for default models ----------------
rng = np.random.default_rng(42)
boot_ci = {}
for name in models:
    yp = preds[name]["test"]
    n = len(y_test)
    vals = []
    for _ in range(2000):
        idx = rng.integers(0, n, n)
        vals.append([
            mean_absolute_error(y_test.iloc[idx], yp[idx]),
            np.sqrt(mean_squared_error(y_test.iloc[idx], yp[idx])),
            r2_score(y_test.iloc[idx], yp[idx]),
        ])
    vals = np.array(vals)
    boot_ci[name] = {
        "MAE": [float(np.percentile(vals[:, 0], 2.5)), float(np.percentile(vals[:, 0], 97.5))],
        "RMSE": [float(np.percentile(vals[:, 1], 2.5)), float(np.percentile(vals[:, 1], 97.5))],
        "R2": [float(np.percentile(vals[:, 2], 2.5)), float(np.percentile(vals[:, 2], 97.5))],
    }
    print("BOOT", name, boot_ci[name], flush=True)

# ---------------- paired tests: linear vs others ----------------
abs_err = {name: np.abs(y_test.values - preds[name]["test"]) for name in models}
paired = {}
for name in ["Random forest", "Decision tree", "Gradient boosting", "Voting regressor"]:
    diff = abs_err["Linear regression"] - abs_err[name]
    stat, p = wilcoxon(abs_err["Linear regression"], abs_err[name])
    boot = []
    for _ in range(2000):
        idx = rng.integers(0, len(diff), len(diff))
        boot.append(np.mean(diff[idx]))
    paired[name] = {
        "mean_diff": float(np.mean(diff)),
        "ci": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
        "p": float(p),
    }
    print("PAIRED", name, paired[name], flush=True)

# ---------------- repeated 5x5 CV ----------------
rkf = RepeatedKFold(n_splits=5, n_repeats=5, random_state=42)
rep_rows = {name: {"MAE": [], "RMSE": [], "R2": []} for name in models}
fold_best = {name: 0 for name in models}
for fold, (tr, te) in enumerate(rkf.split(X, y), 1):
    Xtr, Xte = X.iloc[tr], X.iloc[te]
    ytr, yte = y.iloc[tr], y.iloc[te]
    fold_maes = {}
    for name, model in models.items():
        pipe = Pipeline([("preprocessor", preprocessor), ("model", model)])
        pipe.fit(Xtr, ytr)
        yp = pipe.predict(Xte)
        rep_rows[name]["MAE"].append(mean_absolute_error(yte, yp))
        rep_rows[name]["RMSE"].append(np.sqrt(mean_squared_error(yte, yp)))
        rep_rows[name]["R2"].append(r2_score(yte, yp))
        fold_maes[name] = rep_rows[name]["MAE"][-1]
    best_name = min(fold_maes, key=fold_maes.get)
    fold_best[best_name] += 1
    if fold % 5 == 0:
        print("CV fold", fold, flush=True)

rep_cv = {}
for name in models:
    rep_cv[name] = {
        "MAE_mean": float(np.mean(rep_rows[name]["MAE"])),
        "MAE_std": float(np.std(rep_rows[name]["MAE"])),
        "RMSE_mean": float(np.mean(rep_rows[name]["RMSE"])),
        "RMSE_std": float(np.std(rep_rows[name]["RMSE"])),
        "R2_mean": float(np.mean(rep_rows[name]["R2"])),
        "R2_std": float(np.std(rep_rows[name]["R2"])),
        "best_folds": int(fold_best[name]),
    }
    print("REP", name, rep_cv[name], flush=True)

# ---------------- Table 10: coefficients, permutation importance, VIF ----------------
lin = fitted["Linear regression"]
pre = lin.named_steps["preprocessor"]
feat_names = pre.get_feature_names_out()
coefs = lin.named_steps["model"].coef_
coef_map = {}
for fn, coef in zip(feat_names, coefs):
    if fn.startswith("num__"):
        coef_map[fn.replace("num__", "")] = float(coef)

# Permutation importance for Table 10 is computed by permutation_importance_oof.py
# on out-of-fold validation predictions within the training data.

# VIF on full 215 numeric features
vif = {}
for col in numeric_features:
    others = [c for c in numeric_features if c != col]
    lr = LinearRegression().fit(X[others], X[col])
    r2 = lr.score(X[others], X[col])
    vif[col] = float(1.0 / (1.0 - r2)) if r2 < 1 else float("inf")
print("PERM", perm_map, flush=True)
print("VIF", vif, flush=True)

# ---------------- Table 7 allometry ----------------
def fit_allom(sub):
    x = np.log(sub["Length"].values.astype(float))
    yy = np.log(sub["Weight"].values.astype(float))
    Xd = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(Xd, yy, rcond=None)
    resid = yy - Xd @ beta
    n, k = Xd.shape
    s2 = np.sum(resid ** 2) / (n - k)
    cov = s2 * np.linalg.inv(Xd.T @ Xd)
    se_b = np.sqrt(cov[1, 1])
    tcrit = tdist.ppf(0.975, n - k)
    b = beta[1]
    return {
        "n": int(n), "a": float(np.exp(beta[0])), "b": float(b), "se": float(se_b),
        "ci": [float(b - tcrit * se_b), float(b + tcrit * se_b)],
    }

allom = {}
for label, mask in [
    ("Breed3 Male", (df["group"] == "Chuvash scaled carp") & (df["sex"] == "Male")),
    ("Breed3 Female", (df["group"] == "Chuvash scaled carp") & (df["sex"] == "Female")),
    ("Breed4 Male", (df["group"] == "Petrovsky carp cross") & (df["sex"] == "Male")),
    ("Breed5 Male", (df["group"] == "Anish mirror carp") & (df["sex"] == "Male")),
    ("Breed5 Female", (df["group"] == "Anish mirror carp") & (df["sex"] == "Female")),
    ("All Male", df["sex"] == "Male"),
    ("All Female", df["sex"] == "Female"),
]:
    allom[label] = fit_allom(df[mask])
    print("ALLOM", label, allom[label], flush=True)

# ---------------- save ----------------
out = {
    "results": results,
    "bootstrap": boot_ci,
    "paired": paired,
    "repeated_cv": rep_cv,
    "vif": vif,
    "coefficients": coef_map,
    "allometry": allom,
    "n_train": int(train_mask.sum()),
    "n_test": int(test_mask.sum()),
    "test_ids": df.loc[test_mask, "№"].astype(int).tolist(),
    "y_test": y_test.astype(float).tolist(),
    "predictions": {k: {"test": v["test"].astype(float).tolist()} for k, v in preds.items()},
}
with open(os.path.join(OUT, "results.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

# CSV summary
rows = []
for name, r in results.items():
    rows.append({
        "model": name, "status": r["status"],
        "train_RMSE": r["train_RMSE"], "test_RMSE": r["test_RMSE"],
        "train_MAE": r["train_MAE"], "test_MAE": r["test_MAE"],
        "train_R2": r["train_R2"], "test_R2": r["test_R2"],
        "cv_mean": r["cv_mean"], "cv_std": r["cv_std"],
        "test_MRE": r["test_MRE"], "test_MaxErr": r["test_MaxErr"],
        "test_Acc10": r["test_Acc10"], "test_Acc5": r["test_Acc5"],
    })
pd.DataFrame(rows).to_csv(os.path.join(OUT, "metrics.csv"), index=False)

# ---------------- figures ----------------
plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10})
defaults = ["Linear regression", "Decision tree", "Random forest", "Gradient boosting", "Voting regressor"]

# Figure 5: default models only
fig, axes = plt.subplots(3, 2, figsize=(12, 13))
axes = axes.flatten()
for ax, name in zip(axes, defaults):
    err = y_test.values - preds[name]["test"]
    sns.histplot(err, kde=True, bins=20, ax=ax, color="#4C72B0")
    ax.axvline(0, color="red", linestyle="--", linewidth=2)
    ax.set_xlabel("Prediction error (g)")
    ax.set_ylabel("Frequency")
    ax.set_title(f"{name}\nMean: {err.mean():.1f} g, SD: {err.std():.1f} g")
    ax.grid(True, alpha=0.3)
axes[-1].axis("off")
plt.tight_layout()
fig.savefig(os.path.join(OUT, "Figure5.png"), dpi=150)
plt.close(fig)

# Supplementary Figure S2: tuned variants
tuned = [x + ", tuned" for x in defaults]
fig, axes = plt.subplots(3, 2, figsize=(12, 13))
axes = axes.flatten()
for ax, name in zip(axes, tuned):
    err = y_test.values - preds[name]["test"]
    sns.histplot(err, kde=True, bins=20, ax=ax, color="#4C72B0")
    ax.axvline(0, color="red", linestyle="--", linewidth=2)
    ax.set_xlabel("Prediction error (g)")
    ax.set_ylabel("Frequency")
    ax.set_title(f"{name}\nMean: {err.mean():.1f} g, SD: {err.std():.1f} g")
    ax.grid(True, alpha=0.3)
axes[-1].axis("off")
plt.tight_layout()
fig.savefig(os.path.join(OUT, "Supplementary_Figure_S2.png"), dpi=150)
plt.close(fig)

# Figure 6: observed vs predicted with central-range inset
fig, axes = plt.subplots(3, 2, figsize=(12, 13))
axes = axes.flatten()
for ax, name in zip(axes, defaults):
    yp = preds[name]["test"]
    ax.scatter(y_test, yp, alpha=0.65, s=45, color="#4C72B0", edgecolor="none")
    lo, hi = float(y_test.min()), float(y_test.max())
    ax.plot([lo, hi], [lo, hi], "r--", lw=2)
    ax.set_xlabel("Observed weight (g)")
    ax.set_ylabel("Predicted weight (g)")
    ax.set_title(f"{name}\nR\u00b2 = {r2_score(y_test, yp):.3f}")
    ax.grid(True, alpha=0.3)
    axin = inset_axes(ax, width="45%", height="45%", loc="lower right", borderpad=1.2)
    axin.scatter(y_test, yp, alpha=0.65, s=18, color="#4C72B0", edgecolor="none")
    axin.plot([1500, 4500], [1500, 4500], "r--", lw=1.2)
    axin.set_xlim(1500, 4500)
    axin.set_ylim(1500, 4500)
    axin.tick_params(labelsize=7)
    axin.grid(True, alpha=0.2)
axes[-1].axis("off")
plt.tight_layout()
fig.savefig(os.path.join(OUT, "Figure6.png"), dpi=150)
plt.close(fig)

print("DONE", flush=True)
