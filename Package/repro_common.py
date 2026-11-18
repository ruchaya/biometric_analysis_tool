# -*- coding: utf-8 -*-
"""Shared data loading and model helpers for the reproducibility package."""
import os
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE = os.path.dirname(os.path.abspath(__file__))

GROUP_MAP = {
    "парский зеркальный": "Parsky",
    "чешский чешуйчатый": "Czech",
    "чувашский чешуйчатый": "Chuvash",
    "петровский чешуйчатый": "Petrovsky",
    "анишский зеркальный": "Anish",
    "зеркальный анишский": "Anish",
}

FULL_NUM = [
    "Length", "Commercial_Length", "Girth", "Max_Height", "Age",
    "Volume_Estimate", "Length_Girth_Ratio", "Cross_Section_Area",
]
REDUCED_A_NUM = ["Length", "Girth", "Max_Height", "Age"]
REDUCED_B_NUM = ["Length", "Girth", "Max_Height"]
CAT = ["group", "sex"]


def load_data():
    df = pd.read_csv(os.path.join(BASE, "modeling_data_215.csv"))
    split = pd.read_csv(os.path.join(BASE, "split.csv"))
    df = df.merge(split[["ID", "Split"]], left_on="№", right_on="ID", how="left")
    df["group"] = (df["Примечание"].astype(str).str.strip().str.lower()
                   .str.replace(r"\s+", " ", regex=True).map(GROUP_MAP))
    df["sex"] = df["Пол"].astype(str).str.strip().str.upper().map({"Ж": "Female", "М": "Male"})
    df["Weight"] = pd.to_numeric(df["Вес, г"])
    df["Length"] = pd.to_numeric(df["Длина, см"])
    df["Commercial_Length"] = pd.to_numeric(df["Промыс.длина, см"])
    df["Girth"] = pd.to_numeric(df["Обхват, см"])
    df["Max_Height"] = pd.to_numeric(df["Наиб. Высота, см"])
    df["HL"] = pd.to_numeric(df["Длина гол., см"])
    df["Age"] = pd.to_numeric(df["Возраст, л (по состоянию на весну 2025)"])
    df["Volume_Estimate"] = df["Length"] * df["Girth"] * df["Max_Height"]
    df["Length_Girth_Ratio"] = df["Length"] / df["Girth"]
    df["Cross_Section_Area"] = np.pi * (df["Girth"] / (2 * np.pi)) ** 2
    return df


def make_pipeline(num_features, categorical=True):
    transformers = [("num", Pipeline([("scaler", StandardScaler())]), num_features)]
    if categorical:
        transformers.append(
            ("cat", Pipeline([("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), CAT)
        )
    return Pipeline([("preprocessor", ColumnTransformer(transformers)), ("model", LinearRegression())])


def metrics(y_true, pred):
    err = np.asarray(y_true) - np.asarray(pred)
    return {
        "MAE": float(mean_absolute_error(y_true, pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, pred))),
        "R2": float(r2_score(y_true, pred)),
    }
