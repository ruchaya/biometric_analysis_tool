import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
import sys
import shutil
import json
import queue
import threading
import logging
from logging.handlers import RotatingFileHandler
import gc
import hashlib
import warnings

try:
    from scipy import stats as scipy_stats
except ImportError:  # pragma: no cover - при отсутствии scipy часть статистики недоступна
    scipy_stats = None

# Сужаем подавление предупреждений до известных «шумных» случаев,
# вместо глобального warnings.filterwarnings('ignore').
warnings.filterwarnings('ignore', message='.*Glyph \\d+ .* missing from font.*')
warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*invalid value encountered.*')
warnings.filterwarnings('ignore', message='.*tight_layout.*')

# Настройка темы CustomTkinter
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# Путь к файлу журнала (заполняется при настройке логирования)
LOG_FILE_PATH = None

# Значения по умолчанию для формул/регрессии (можно менять в интерфейсе)
FULTON_LENGTH_DEFAULT = 'fishing'   # 'fishing' (промысловая) или 'total' (общая)
REGRESSION_X_DEFAULT = 'TotalLength'
REGRESSION_Y_DEFAULT = 'Weight'

# Метаданные приложения
APP_NAME = "Анализ биометрических индексов"
APP_VERSION = "1.0"
APP_AUTHOR = "ВНИИР"
ICON_RELATIVE = os.path.join("assets", "bioanalizator.ico")
LOGO_RELATIVE = os.path.join("assets", "bioanalizator.png")

# Шаблон таблицы для заполнения данными
TEMPLATE_COLUMNS = [
    "№", "№ чипа", "№ пробирки", "Пол",
    "Вес, г", "Длина, см", "Промыс.длина, см",
    "Длина головы, см", "Обхват, см", "Наиб. высота, см",
    "Кол-во лучей в СП", "Кол-во лучей в АП", "Примечание",
]

TEMPLATE_EXAMPLES = [
    {"№": 1, "№ чипа": "A-0001", "№ пробирки": "T-001", "Пол": "M",
     "Вес, г": 320.5, "Длина, см": 28.4, "Промыс.длина, см": 26.0,
     "Длина головы, см": 6.1, "Обхват, см": 16.2, "Наиб. высота, см": 8.4,
     "Кол-во лучей в СП": 9, "Кол-во лучей в АП": 3, "Примечание": "пример"},
    {"№": 2, "№ чипа": "A-0002", "№ пробирки": "T-002", "Пол": "F",
     "Вес, г": 245.0, "Длина, см": 25.1, "Промыс.длина, см": 23.3,
     "Длина головы, см": 5.4, "Обхват, см": 14.5, "Наиб. высота, см": 7.6,
     "Кол-во лучей в СП": 9, "Кол-во лучей в АП": 3, "Примечание": "пример"},
    {"№": 3, "№ чипа": "", "№ пробирки": "", "Пол": "",
     "Вес, г": 410.2, "Длина, см": 31.0, "Промыс.длина, см": 28.7,
     "Длина головы, см": "", "Обхват, см": "", "Наиб. высота, см": "",
     "Кол-во лучей в СП": "", "Кол-во лучей в АП": "", "Примечание": ""},
]

# (колонка, обязательность, единицы, описание)
TEMPLATE_HELP = [
    ("№", "нет", "-", "Порядковый номер образца"),
    ("№ чипа", "нет", "-", "Номер чипа / метки"),
    ("№ пробирки", "нет", "-", "Номер пробирки"),
    ("Пол", "нет", "-", "Пол особи (M / F)"),
    ("Вес, г", "да", "г", "Живая масса"),
    ("Длина, см", "нет", "см", "Общая длина (если не указать — используется промысловая)"),
    ("Промыс.длина, см", "да", "см", "Промысловая длина"),
    ("Длина головы, см", "нет", "см", "Для индекса длинноголовости"),
    ("Обхват, см", "нет", "см", "Обхват тела"),
    ("Наиб. высота, см", "нет", "см", "Для индекса прогонистости"),
    ("Кол-во лучей в СП", "нет", "шт", "Число лучей в спинном плавнике"),
    ("Кол-во лучей в АП", "нет", "шт", "Число лучей в анальном плавнике"),
    ("Примечание", "нет", "-", "Группа / примечание (используется для группировки)"),
]


def resource_path(relative_path):
    """Возвращает путь к ресурсу как в исходниках, так и в собранном exe."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate = os.path.join(base, relative_path)
        if os.path.exists(candidate):
            return candidate
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(project_root, relative_path)
    if os.path.exists(candidate):
        return candidate
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def setup_logging():
    """Настраивает logging: вывод в консоль и в файл рядом с программой."""
    global LOG_FILE_PATH

    log = logging.getLogger("bioanalizator")
    log.setLevel(logging.DEBUG)
    if log.handlers:
        return log

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Кириллица в консоли Windows: принудительно UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    # В pythonw консоли может не быть (sys.stderr = None)
    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        log.addHandler(console)

    # Журнал пишем в рабочий каталог, а при отсутствии прав - в домашний
    candidates = [
        os.path.join(os.getcwd(), "bioanalizator.log"),
        os.path.join(os.path.expanduser("~"), "bioanalizator.log"),
    ]

    file_handler = None
    for path in candidates:
        try:
            file_handler = RotatingFileHandler(
                path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
            LOG_FILE_PATH = path
            break
        except OSError:
            continue

    if file_handler is not None:
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        log.addHandler(file_handler)

    log.info("Логирование инициализировано. Файл журнала: %s", LOG_FILE_PATH)
    return log


logger = setup_logging()


class TaskCancelled(Exception):
    """Пользователь отменил фоновую операцию."""


def _is_missing(value):
    """Безопасная проверка на NaN/None (значения в таблицах всегда скаляры)."""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def wrap_text(text, max_line_length=15):
    """Переносит длинный заголовок по словам."""
    words = str(text).split()
    lines = []
    current_line = ""

    for word in words:
        if len(current_line) + len(word) <= max_line_length:
            current_line = f"{current_line} {word}".strip()
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)


def format_value(column, value):
    """Форматирование значений таблиц результатов."""
    if _is_missing(value):
        return ""
    if isinstance(value, (bool, np.bool_)):
        return str(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        decimals = 4 if 'индекс' in str(column).lower() else 2
        return round(float(value), decimals)
    return value


def format_regression(column, value):
    """Форматирование коэффициентов регрессии с повышенной точностью."""
    if _is_missing(value):
        return ""
    name = str(column).lower()
    if isinstance(value, (float, np.floating)):
        if 'p_value' in name or 'p-value' in name or name.strip() == 'p':
            return f"{float(value):.3g}"
        return round(float(value), 6)
    if isinstance(value, (int, np.integer)):
        return int(value)
    return value


def format_raw(column, value):
    """Форматирование исходных данных (максимально близко к оригиналу)."""
    if _is_missing(value):
        return ""
    if isinstance(value, (float, np.floating)):
        return round(float(value), 4)
    if isinstance(value, (int, np.integer)):
        return int(value)
    return value


# Соответствие внутренних полей и подписей для автоопределения колонок.
COLUMN_FIELD_LABELS = [
    ('number_col', '№'),
    ('chip_col', '№ чипа'),
    ('tube_col', '№ пробирки'),
    ('weight_col', 'Вес, г'),
    ('total_length_col', 'Длина, см'),
    ('fishing_length_col', 'Промыс.длина, см'),
    ('head_length_col', 'Длина гол., см'),
    ('girth_col', 'Обхват, см'),
    ('body_height_col', 'Наиб. Высота, см'),
    ('dorsal_rays_col', 'Кол-во лучей в СП'),
    ('anal_rays_col', 'Кол-во лучей в АП'),
    ('notes_col', 'Примечание'),
    ('sex_col', 'Пол'),
]

# Соответствие внутренних имён колонок и подписей в экспорте/таблицах.
COLUMN_RENAME_MAP = {
    'Number': '№', 'ChipNumber': '№ чипа', 'TubeNumber': '№ пробирки',
    'Weight': 'Вес, г', 'TotalLength': 'Длина, см',
    'FishingLength': 'Промыс.длина, см', 'HeadLength': 'Длина гол., см',
    'Girth': 'Обхват, см', 'BodyHeight': 'Наиб. Высота, см',
    'DorsalRays': 'Кол-во лучей в СП', 'AnalRays': 'Кол-во лучей в АП',
    'FultonIndex': 'Индекс Фультона',
    'PhysicalDevelopmentIndex': 'Индекс физ.развития',
    'Относит_вес': 'Относит.вес', 'CephalicIndex': 'Длинноголовость, %',
    'BodyShapeIndex': 'Прогонистость, %', 'Sex': 'Пол', 'Notes': 'Примечание',
}

# Короткие русские подписи признаков для таблиц/графиков/экспорта
FEATURE_LABELS = {
    'Weight': 'Вес, г',
    'TotalLength': 'Длина, см',
    'FishingLength': 'Промыс.длина',
    'HeadLength': 'Длина головы',
    'Girth': 'Обхват',
    'BodyHeight': 'Наиб. высота',
    'DorsalRays': 'Лучи СП',
    'AnalRays': 'Лучи АП',
    'FultonIndex': 'Индекс Фультона',
    'PhysicalDevelopmentIndex': 'Индекс физ.развития',
    'Относит_вес': 'Относит.вес',
    'CephalicIndex': 'Длинноголовость',
    'BodyShapeIndex': 'Прогонистость',
    'Number': '№',
    'ChipNumber': '№ чипа',
    'TubeNumber': '№ пробирки',
    'Sex': 'Пол',
    'Notes': 'Примечание',
}

GROUP_LABELS = {'Sex': 'Пол', 'Notes': 'Примечание'}


def feature_label(name):
    """Русская подпись признака (для отображения и экспорта)."""
    return FEATURE_LABELS.get(name, str(name))


# Профиль сопоставления колонок (JSON)
PROFILE_VERSION = 1


def save_profile(path, mapping, options):
    """Сохраняет профиль сопоставления колонок и настроек в JSON."""
    payload = {
        'version': PROFILE_VERSION,
        'mapping': mapping,
        'options': options,
        'saved_at': pd.Timestamp.now().isoformat(timespec='seconds'),
    }
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def load_profile(path):
    """Читает профиль сопоставления колонок. Возвращает (mapping, options)."""
    with open(path, encoding='utf-8') as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("Некорректный файл профиля")
    mapping = payload.get('mapping') or {}
    options = payload.get('options') or {}
    if not isinstance(mapping, dict) or not isinstance(options, dict):
        raise ValueError("Некорректная структура профиля")
    return mapping, options


# Шаблоны поиска колонок: (pattern, exclude)
COLUMN_DETECTION = {
    # pattern может быть строкой или списком; exclusion - список подстрок
    'number_col': (["номер", "№", "п/п"], ["чип", "пробирк"]),
    'chip_col': (["чипа", "чип"], ["пробирк"]),
    'tube_col': (["пробирк"], []),
    'weight_col': (["вес", "масса"], []),
    'total_length_col': (["длина"], ["промыс", "гол", "голов"]),
    'fishing_length_col': (["промыс"], []),
    'head_length_col': (["гол"], []),
    'girth_col': (["обхват"], []),
    'body_height_col': (["высота"], []),
    'dorsal_rays_col': (["сп", "спинн"], []),
    'anal_rays_col': (["ап", "анальн"], []),
    'notes_col': (["приме", "групп"], []),
    'sex_col': (["пол"], ["половин"]),
}
