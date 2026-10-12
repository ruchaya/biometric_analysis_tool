"""Точка входа приложения «Анализ биометрических индексов»."""
import os
import sys


def _run_selftest():
    """Проверка, что все зависимости доступны в собранном виде (без GUI)."""
    import tempfile
    import numpy as np
    import pandas as pd

    from bioanalizator.core import BiometricAnalysis

    rng = np.random.default_rng(0)
    n = 20
    length = np.linspace(16, 36, n)
    weight = 0.01 * length ** 3 * np.exp(rng.normal(0, 0.05, n))
    raw = pd.DataFrame({
        "Номер": range(1, n + 1),
        "Вес": weight,
        "Длина": length,
        "Промыс.длина": length * 0.9,
        "Пол": ["M", "F"] * (n // 2),
    })

    an = BiometricAnalysis()
    an.data = raw
    mapping = {key: "" for key in [
        "number_col", "chip_col", "tube_col", "weight_col", "total_length_col",
        "fishing_length_col", "head_length_col", "girth_col", "body_height_col",
        "dorsal_rays_col", "anal_rays_col", "notes_col", "sex_col"]}
    mapping.update({
        "number_col": "Номер", "weight_col": "Вес", "total_length_col": "Длина",
        "fishing_length_col": "Промыс.длина", "sex_col": "Пол",
    })
    assert an.calculate_indices(mapping, {"regression_x": "Длина", "regression_y": "Вес"})
    assert an.regression_coefficients is not None and not an.regression_coefficients.empty

    # проверка чтения/записи Excel (openpyxl)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "selftest.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            an.clean_data.to_excel(writer, sheet_name="Данные", index=False)
        assert len(pd.read_excel(path, sheet_name="Данные")) == len(an.clean_data)

        # проверка шаблона
        from bioanalizator.app import BiometricApp
        template = os.path.join(tmp, "template.xlsx")
        BiometricApp._write_template(template)
        sheets = pd.read_excel(template, sheet_name=None)
        assert "Данные" in sheets and "Инструкция" in sheets

    # проверка matplotlib (построение фигуры без GUI)
    fig = an.create_plot("length_weight", show_ci=True)
    assert fig is not None

    return 0


def main():
    if "--selftest" in sys.argv or os.environ.get("BIOANALIZATOR_SELFTEST"):
        try:
            code = _run_selftest()
        except Exception as exc:  # noqa: BLE001
            import traceback
            message = f"FAIL: {exc}\n{traceback.format_exc()}"
            code = 1
        else:
            message = "OK: все зависимости доступны"
        try:
            with open(os.path.join(os.getcwd(), "selftest_result.txt"), "w", encoding="utf-8") as fh:
                fh.write(message)
        except OSError:
            pass
        raise SystemExit(code)

    from bioanalizator.app import BiometricApp

    app = BiometricApp()
    app.mainloop()


if __name__ == "__main__":
    main()
