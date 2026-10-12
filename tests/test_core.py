"""Тесты ядра: очистка данных, индексы, регрессии, корреляции."""
import numpy as np
import pandas as pd
from scipy import stats as st

from bioanalizator.core import BiometricAnalysis
from conftest import make_mapping


def test_numeric_coercion_and_no_data_loss():
    raw = pd.DataFrame({
        "Вес": ["100,5", "200", "abc", "150"],
        "Промыс.длина": [18, 23, 27, 20],
        "Пол": ["M", None, "F", ""],
        "Примечание": ["A", "A", None, "B"],
    })
    an = BiometricAnalysis()
    an.data = raw
    mapping = make_mapping(weight_col="Вес", fishing_length_col="Промыс.длина",
                           sex_col="Пол", notes_col="Примечание")
    assert an.calculate_indices(mapping)
    assert an.clean_data["Weight"].dtype.kind == "f"
    # строка с "abc" отброшена, остальные сохранены несмотря на пропуски Sex/Notes
    assert an.filter_info == {"total": 4, "kept": 3, "removed": 1}
    # строка с полом "F" отброшена из-за нечислового веса; "" -> "Не указано"
    assert set(an.clean_data["Sex"]) == {"M", "Не указано"}


def test_rejected_reasons_and_report():
    raw = pd.DataFrame({
        "Вес": [-5, np.nan, 100, 120],
        "Промыс.длина": [0, 18, "abc", 20],
    })
    an = BiometricAnalysis()
    an.data = raw
    an.calculate_indices(make_mapping(weight_col="Вес", fishing_length_col="Промыс.длина"))
    assert an.rejected_data is not None and len(an.rejected_data) == 3
    reasons = " | ".join(an.rejected_data["Причина"].astype(str))
    assert "вес ≤ 0" in reasons
    assert "промысловая длина ≤ 0" in reasons
    assert "вес отсутствует" in reasons


def test_power_regression_statistics_and_cache(analyzer):
    reg = analyzer.calculate_power_regression(analyzer.clean_data, "TotalLength", "Weight")
    for key in ("a", "b", "r_squared", "se_b", "b_ci_low", "b_ci_high",
                "p_value", "p_value_b3", "n"):
        assert reg[key] is not None, key
    assert reg["b_ci_low"] < reg["b"] < reg["b_ci_high"]

    # сверка с scipy
    logx = np.log(analyzer.clean_data["TotalLength"])
    logy = np.log(analyzer.clean_data["Weight"])
    lr = st.linregress(logx, logy)
    assert abs(reg["b"] - lr.slope) < 1e-9
    assert abs(reg["se_b"] - lr.stderr) < 1e-9
    assert abs(reg["p_value"] - lr.pvalue) < 1e-12

    # кэш: тот же объект и не зависит от порядка строк
    assert analyzer.calculate_power_regression(analyzer.clean_data, "TotalLength", "Weight") is reg
    shuffled = analyzer.clean_data.sample(frac=1.0, random_state=1)
    assert analyzer.calculate_power_regression(shuffled, "TotalLength", "Weight") is reg


def test_confidence_band(analyzer):
    reg = analyzer.calculate_power_regression(analyzer.clean_data, "TotalLength", "Weight")
    band = analyzer.power_regression_band(np.linspace(16, 38, 20), reg)
    assert band is not None
    grid, lower, upper = band
    assert len(grid) == 20
    assert np.all(lower < upper)


def test_fulton_length_basis(analyzer, sample_raw):
    an = BiometricAnalysis()
    an.data = sample_raw
    mapping = make_mapping(weight_col="Вес", total_length_col="Длина",
                           fishing_length_col="Промыс.длина")
    an.calculate_indices(mapping, {"fulton_length": "fishing"})
    fishing = an.clean_data["FultonIndex"].mean()
    an.calculate_indices(mapping, {"fulton_length": "total"})
    total = an.clean_data["FultonIndex"].mean()
    assert abs(fishing - total) > 1e-9


def test_regression_variable_selection(analyzer):
    analyzer.calculate_indices(
        make_mapping(weight_col="Вес", total_length_col="Длина",
                     fishing_length_col="Промыс.длина"),
        {"regression_x": "FishingLength", "regression_y": "Weight"},
    )
    assert analyzer.regression_x_var == "FishingLength"
    assert analyzer.regression_coefficients is not None


def test_find_column_number_variants():
    data = pd.DataFrame(columns=["№", "№ чипа", "№ пробирки", "Вес, г", "Промыс.длина, см"])
    an = BiometricAnalysis()
    number_pattern, number_exclude = None, None
    from bioanalizator.common import COLUMN_DETECTION
    number_pattern, number_exclude = COLUMN_DETECTION["number_col"]
    assert an.find_column(number_pattern, data, exclude=number_exclude) == "№"
    assert an.find_column("номер", data) is None
    # «№» не должен перехватывать «№ чипа» / «№ пробирки»
    chip_pattern, chip_exclude = COLUMN_DETECTION["chip_col"]
    assert an.find_column(chip_pattern, data, exclude=chip_exclude) == "№ чипа"
    tube_pattern, tube_exclude = COLUMN_DETECTION["tube_col"]
    assert an.find_column(tube_pattern, data, exclude=tube_exclude) == "№ пробирки"


def test_regression_resolves_source_column_names(sample_raw):
    """Регрессия должна считаться, когда X/Y заданы исходными именами колонок."""
    an = BiometricAnalysis()
    an.data = sample_raw
    mapping = make_mapping(weight_col="Вес", total_length_col="Длина",
                           fishing_length_col="Промыс.длина",
                           sex_col="Пол", notes_col="Примечание")
    assert an.calculate_indices(mapping, {"regression_x": "Длина", "regression_y": "Вес"})
    assert an.regression_x_var == "TotalLength"
    assert an.regression_y_var == "Weight"
    assert an.regression_coefficients is not None
    assert not an.regression_coefficients.empty
    assert an.regression_coefficients["p_value"].notna().any()


def test_custom_plot_with_source_columns(analyzer):
    """Произвольный график строится по исходным колонкам данных."""
    fig = analyzer.create_plot("custom", x_var="Промыс.длина", y_var="Вес", show_ci=True)
    assert fig is not None
    assert len(fig.axes) == 1


def test_correlation_matrix_russian_labels(analyzer):
    corr = analyzer.get_correlation_matrix()
    assert corr is not None and abs(corr.loc["TotalLength", "Weight"]) > 0.9
    assert "Number" not in corr.columns

    display = analyzer.get_correlation_display()
    assert display is not None
    assert "Вес, г" in display.index and "Weight" not in display.index
    assert display.iloc[0, 0] == "1.00"
    assert display.loc["Вес, г", "Длина, см"].endswith("*")
