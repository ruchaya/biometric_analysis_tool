"""Тесты описательной статистики и сравнения групп."""


def test_extended_summary_statistics(analyzer):
    stats = analyzer.get_summary_statistics()
    labels = set(stats["Показатель"])
    for expected in (
        "Вес, г (медиана)", "Вес, г (ст.откл)", "Вес, г (CV, %)",
        "Вес, г (Q1)", "Вес, г (Q3)",
        "Вес, г (95% ДИ низ)", "Вес, г (95% ДИ верх)",
    ):
        assert expected in labels, expected
    # категории
    assert "Общая информация" in set(stats["Категория"])
    assert "Входные данные" in set(stats["Категория"])


def test_group_statistics_russian(analyzer):
    group_stats = analyzer.get_group_statistics()
    assert group_stats is not None
    assert set(group_stats["Группировка"]) == {"Пол", "Примечание"}
    assert {"Вес, г", "Длина, см"} & set(group_stats["Признак"])
    assert "Weight" not in set(group_stats["Признак"])
    assert {"n", "средн", "ст.откл", "медиана", "CI_низ", "CI_верх"}.issubset(group_stats.columns)


def test_compare_groups(analyzer):
    compare = analyzer.compare_groups()
    assert compare is not None
    assert {"Группировка", "Признак", "Тест", "Статистика", "p-value",
            "p_adj (BH)", "значимо"}.issubset(compare.columns)
    assert compare["p-value"].between(0, 1).all()
    assert compare["p_adj (BH)"].between(0, 1).all()
    tests = set(compare["Тест"])
    assert "t-тест Уэлча" in tests and "Манн–Уитни" in tests
    assert set(compare["Группировка"]) == {"Пол", "Примечание"}
