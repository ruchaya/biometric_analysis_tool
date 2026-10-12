"""Тесты импорта/экспорта, профиля и русских подписей."""
import pandas as pd

from bioanalizator import common
from bioanalizator.core import BiometricAnalysis


def test_excel_sheet_selection(tmp_path):
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"A": [1, 2, 3]}).to_excel(writer, sheet_name="Первый", index=False)
        pd.DataFrame({"B": [9, 8, 7, 6]}).to_excel(writer, sheet_name="Второй", index=False)

    an = BiometricAnalysis()
    assert an.list_excel_sheets(path) == ["Первый", "Второй"]
    an.load_data(file_path=str(path), sheet_name="Второй")
    assert list(an.data.columns) == ["B"] and len(an.data) == 4
    an.load_data(file_path=str(path))
    assert list(an.data.columns) == ["A"]


def test_csv_autodetect_and_cp1251(tmp_path):
    path = tmp_path / "data.csv"
    with open(path, "w", encoding="cp1251", newline="") as fh:
        fh.write("Вес;Промыс.длина;Пол\n")
        fh.write("100;20;M\n200;25;F\n")
    an = BiometricAnalysis()
    an.load_data(file_path=str(path))
    assert len(an.data) == 2
    assert {"Вес", "Промыс.длина", "Пол"}.issubset(an.data.columns)
    assert an.data["Вес"].tolist() == [100, 200]


def test_mapping_profile_roundtrip(tmp_path):
    path = tmp_path / "profile.json"
    mapping = {"weight_col": "Вес", "fishing_length_col": "Промыс.длина", "sex_col": "Пол"}
    options = {"fulton_length": "total", "regression_x": "Промыс.длина", "regression_y": "Вес"}
    common.save_profile(str(path), mapping, options)
    loaded_mapping, loaded_options = common.load_profile(str(path))
    assert loaded_mapping == mapping
    assert loaded_options == options


def test_excel_template(tmp_path):
    from bioanalizator.app import BiometricApp

    path = tmp_path / "template.xlsx"
    BiometricApp._write_template(str(path))
    sheets = pd.read_excel(path, sheet_name=None)
    assert "Данные" in sheets and "Инструкция" in sheets
    assert list(sheets["Данные"].columns) == common.TEMPLATE_COLUMNS
    assert len(sheets["Данные"]) == len(common.TEMPLATE_EXAMPLES)
    assert set(common.TEMPLATE_COLUMNS) == set(sheets["Инструкция"]["Колонка"])


def test_feature_labels_russian():
    assert common.feature_label("Weight") == "Вес, г"
    assert common.feature_label("FultonIndex") == "Индекс Фультона"
    # неизвестное имя возвращается как есть
    assert common.feature_label("Custom") == "Custom"
