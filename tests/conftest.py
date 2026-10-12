"""Общие фикстуры и настройки тестов."""
import os
import sys
import time

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

# пакет лежит в корне проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bioanalizator.core import BiometricAnalysis  # noqa: E402

COLUMN_KEYS = [
    "number_col", "chip_col", "tube_col", "weight_col", "total_length_col",
    "fishing_length_col", "head_length_col", "girth_col", "body_height_col",
    "dorsal_rays_col", "anal_rays_col", "notes_col", "sex_col",
]


def make_mapping(**overrides):
    mapping = {key: "" for key in COLUMN_KEYS}
    mapping.update(overrides)
    return mapping


@pytest.fixture
def sample_raw():
    rng = np.random.default_rng(42)
    n = 40
    length = np.linspace(16, 38, n)
    weight = 0.01 * length ** 3 * np.exp(rng.normal(0, 0.05, n))
    return pd.DataFrame({
        "Номер": range(1, n + 1),
        "Вес": weight,
        "Длина": length,
        "Промыс.длина": length * 0.9,
        "Пол": ["M", "F"] * (n // 2),
        "Примечание": ["A"] * 20 + ["B"] * 20,
    })


@pytest.fixture
def analyzer(sample_raw):
    an = BiometricAnalysis()
    an.data = sample_raw
    mapping = make_mapping(
        number_col="Номер", weight_col="Вес", total_length_col="Длина",
        fishing_length_col="Промыс.длина", sex_col="Пол", notes_col="Примечание",
    )
    assert an.calculate_indices(mapping)
    return an


@pytest.fixture
def app(monkeypatch):
    tkinter = pytest.importorskip("tkinter")
    from bioanalizator import app as app_module

    class DummyMessagebox:
        def showinfo(self, *a, **k):
            pass

        def showerror(self, *a, **k):
            pass

        def showwarning(self, *a, **k):
            pass

        def askyesno(self, *a, **k):
            return True

    monkeypatch.setattr(app_module, "messagebox", DummyMessagebox())
    last_error = None
    application = None
    for _ in range(3):
        try:
            application = app_module.BiometricApp()
            break
        except tkinter.TclError as exc:
            last_error = exc
            time.sleep(0.2)
    if application is None:
        pytest.skip(f"Tk недоступен: {last_error}")
    application.withdraw()
    yield application
    try:
        application.destroy()
    except Exception:
        pass
