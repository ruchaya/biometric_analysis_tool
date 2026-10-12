"""Тесты интерфейса: автозаполнение, таблицы, тема, отмена, графики, экспорт."""
import time

import pandas as pd

from bioanalizator import app as app_module


def pump(application, predicate, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        application.update()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _prepare(app, analyzer):
    app.analyzer = analyzer
    app.analyzer.cancel_check = app._raise_if_cancelled


def test_autofill_and_tables(app, sample_raw):
    app.analyzer.data = sample_raw
    app.update_columns_info()
    app.update_column_comboboxes()
    app.update_data_table()

    assert app.column_vars["weight_col"].get() == "Вес"
    assert app.column_vars["total_length_col"].get() == "Длина"
    assert app.column_vars["fishing_length_col"].get() == "Промыс.длина"
    assert app.column_vars["sex_col"].get() == "Пол"
    assert app.data_table.view_df is not None
    assert len(app.data_table.view_df) == len(sample_raw)


def test_number_column_autodetect(app):
    """Колонка «№» должна определяться автоопределением (частый случай)."""
    app.analyzer.data = pd.DataFrame({
        "№": [1, 2, 3],
        "№ чипа": ["a", "b", "c"],
        "№ пробирки": ["t1", "t2", "t3"],
        "Вес, г": [100.0, 200.0, 300.0],
        "Промыс.длина, см": [18.0, 22.0, 26.0],
    })
    detected = app.detect_columns()
    assert detected["number_col"] == "№"
    assert detected["chip_col"] == "№ чипа"
    assert detected["tube_col"] == "№ пробирки"
    assert detected["weight_col"] == "Вес, г"


def test_column_search_and_sorting(app, sample_raw):
    app.data_table.set_data(sample_raw)
    app.data_table.search_column = "Пол"
    app.data_table.search_term = "F"
    app.data_table.render()
    assert (app.data_table.view_df["Пол"] == "F").all()
    assert len(app.data_table.view_df) == (sample_raw["Пол"] == "F").sum()

    app.data_table.clear_filter()
    app.data_table.sort_by("Вес")
    # сортировка выполняется по исходным значениям DataFrame
    assert app.data_table.view_df["Вес"].iloc[0] == sample_raw["Вес"].min()


def test_theme_toggle(app):
    before = app_module.ctk.get_appearance_mode()
    app.toggle_theme()
    assert app_module.ctk.get_appearance_mode() != before
    app.toggle_theme()
    assert app_module.ctk.get_appearance_mode() == before


def test_task_cancellation(app):
    state = {}

    def slow():
        start = time.time()
        while time.time() - start < 5:
            app._raise_if_cancelled()
            time.sleep(0.02)
        return "late"

    app.run_task(slow, on_success=lambda r: state.update(result=r), description="Тест отмены")
    pump(app, lambda: app._busy, timeout=1.0)
    app.cancel_task()
    assert pump(app, lambda: not app._busy)
    assert "result" not in state


def test_regression_table_after_calculation(app, sample_raw):
    """Полный поток: загрузка -> автозаполнение -> расчёт -> непустая регрессия."""
    app.analyzer.data = sample_raw
    app.update_columns_info()
    app.update_column_comboboxes()

    app.calculate_indices()
    assert pump(app, lambda: not app._busy)
    assert app.analyzer.regression_coefficients is not None
    assert not app.analyzer.regression_coefficients.empty

    app.update_regression_table()
    assert app.regression_table.view_df is not None
    assert len(app.regression_table.view_df) > 0


def test_repeated_plot_in_background(app, analyzer):
    _prepare(app, analyzer)
    for _ in range(3):
        app.create_plot()
        assert pump(app, lambda: not app._busy)
        assert app.current_fig is not None
        assert app.analyzer.current_plot is not None


def test_export_all_results(app, analyzer, tmp_path, monkeypatch):
    _prepare(app, analyzer)
    out = tmp_path / "result.xlsx"
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda *a, **k: str(out))
    app.save_all_results()
    assert pump(app, lambda: not app._busy)
    sheets = pd.read_excel(out, sheet_name=None)
    assert "Данные_с_индексами" in sheets
    assert "Сводная_статистика" in sheets
    assert "Коэффициенты_регрессии" in sheets
    assert "Корреляционная_матрица" in sheets
    assert "Статистика_по_группам" in sheets
