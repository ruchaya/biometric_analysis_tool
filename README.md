# Bioanalizator - Fish Biometric Data Analysis

**Version:** 1.0  
**Software metadata author:** ВНИИР (VNIIR)  
**Implementation:** Python desktop application with a CustomTkinter graphical interface  
**Repository:** https://github.com/ruchaya/biometric_analysis_tool

Bioanalizator is a desktop application for processing individual fish morphometric records. It brings spreadsheet import, biometric-index calculation, descriptive and group-level statistics, length–weight allometric regression, correlation analysis, visualisation, and Excel reporting into a single workflow. The interface and generated report labels are primarily in Russian.

The software can be used to analyse common carp (*Cyprinus carpio*) records, including breeding-group and sex-specific data. Its calculations are based on user-supplied measurements rather than image acquisition or automated sensing.

> **Scope and reproducibility notice:** This source-code package implements biometric data analysis and **power-law (allometric) regression**. It does **not** contain the five-model supervised-learning benchmark (linear regression, decision tree, random forest, gradient boosting, and voting regressor), its training/test splits, hyperparameter searches, or the predictive-performance results reported in the manuscript. **Measured live weight is a required input** for the current application; this version does not estimate the weight of an unweighed fish from morphometric measurements alone. The original research dataset is not included in this archive.

## Related manuscript

*Morphometric Live-Weight Prediction in Common Carp Breeding Populations: A Python-Based Biometric Tool with Comparative Machine-Learning Models* (manuscript; publication DOI and bibliographic metadata have not been supplied). The present archive documents the biometric-analysis component and should not be cited as a complete implementation of the manuscript’s comparative machine-learning experiment.

## Features

- **Data import:** Excel workbooks (with sheet selection) and CSV files, including UTF-8 and Windows-1251 text; automatic delimiter detection when not specified.
- **Data preparation:** suggested column mapping with manual correction; saved and reusable JSON mapping profiles; conversion of numerical fields; exclusion report explaining rejected rows.
- **Biometric indices:** Fulton condition factor, physical development index, relative weight, relative head length, and relative body elongation (see formulas below).
- **Descriptive statistics:** number of observations, minimum, maximum, mean, median, standard deviation, coefficient of variation, quartiles, and 95% confidence intervals.
- **Group analysis:** summaries by sex and by the grouping field (`Notes`), with Welch's *t* test, Mann–Whitney U test, one-way ANOVA, or Kruskal–Wallis test as applicable, including Benjamini–Hochberg-adjusted *p* values.
- **Allometric models:** log–log ordinary least-squares fitting of `y = a × x^b`, with coefficient estimates, goodness of fit, standard errors, confidence intervals where estimable, and tests of `b = 3`.
- **Exploratory analysis:** Pearson correlation matrix, heat map, length–weight plots, index plots, and configurable X–Y plots; optional confidence bands for fitted power regressions.
- **Reporting:** export of measurements and indices, statistics, regression coefficients, correlations, group comparisons, and rejected observations to Excel.
- **Desktop usability:** paginated searchable tables, light/dark appearance modes, cancellable background tasks, and application logging.

## Requirements

- Python **3.10 or newer** (as declared in `pyproject.toml`).
- A desktop environment capable of running Python Tk/CustomTkinter applications.
- Windows is the documented platform for the included `install.bat`, `run.bat`, and executable-building script. Other operating systems may require additional GUI setup; their compatibility has not been verified for this release.

The direct Python dependencies are specified in [`requirements.txt`](requirements.txt):

`customtkinter`, `pandas`, `numpy`, `matplotlib`, `Pillow`, `openpyxl`, `xlrd`, and `scipy`.

The requirement ranges are **not an exact dependency lockfile**; package versions may differ between installations.

## Installation and launch

### Windows: provided scripts

Clone or download the repository, then run the following from the project root:

```powershell
.\install.bat
.\run.bat
```

`install.bat` installs the dependencies using the detected Python interpreter; `run.bat` checks key packages and launches the GUI.

### Manual installation

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

If PowerShell activation is restricted, use `.\.venv\Scripts\python.exe` directly for the installation and launch commands. On other platforms, use the appropriate Python virtual-environment activation syntax. The alternative entry point `python Bioanalizator.py` launches the same GUI.

## Input data

Use **“Скачать шаблон Excel”** (Download Excel template) in the application to generate a sample workbook containing the sheets `Данные` (Data) and `Инструкция` (Instructions). The template includes illustrative records; replace these with actual observations before analysis.

The main supported fields are:

| Field in the supplied template | Required | Unit or purpose |
| --- | --- | --- |
| `Вес, г` | Yes | Measured live weight, g |
| `Промыс.длина, см` | Yes | Commercial/fishing length, cm |
| `Длина, см` | No | Additional recorded length, cm; defaults to commercial length if absent |
| `Длина головы, см` | No | Head length, cm |
| `Обхват, см` | No | Body girth, cm |
| `Наиб. высота, см` | No | Maximum body height, cm |
| `Пол` | No | Sex, e.g., `M` or `F` |
| `Примечание` | No | Group/breeding-line label or notes; used for grouping |
| `Кол-во лучей в СП`, `Кол-во лучей в АП` | No | Dorsal- and anal-fin ray counts |
| `№`, `№ чипа`, `№ пробирки` | No | Record and sample identifiers |

The original spreadsheet headers may differ: use the mapping controls to assign the required program variables. Missing, non-numeric, or non-positive weight and commercial-length values cause a record to be rejected; rejected records and reasons can be exported. All physical units should be consistent with the equations below.

## Typical workflow

1. Download and complete the Excel template, or prepare a compatible Excel/CSV file.
2. Load a file and, if needed, select the Excel worksheet.
3. Review the automatically proposed field assignments and adjust them manually.
4. Choose the length definition used for Fulton’s index and the X/Y variables for power-law regression.
5. Calculate biometric indices; inspect the rejected-record report and sample counts.
6. Review individual records, descriptive statistics, group comparisons, correlations, and allometric regressions.
7. Produce the desired figures and export the analysis to an Excel workbook.

## Implemented calculations

Let `W` denote **measured live weight in grams**, `L_f` commercial/fishing length in centimetres, `L_t` the additional recorded length in centimetres, `HL` head length in centimetres, and `H` maximum body height in centimetres.

| Indicator | Formula in this implementation |
| --- | --- |
| Fulton condition factor | `K = 100 × W / L³`, where `L = L_f` by default and can be changed to `L_t` |
| Physical development index | `PDI = W × L_f / 100` |
| Relative weight | `RW = 1000 × W / L_f` |
| Relative head length | `LHI = 100 × HL / L_f` |
| Body elongation index | `RI = 100 × L_f / H` |

**Important:** The numerical scaling of these indices is implementation-specific. Do not compare them with values computed from different units or index definitions without conversion. The biological definitions of the measured length landmarks should be checked against the sampling protocol before making cross-study comparisons.

Allometric regression fits the relationship

```text
y = a × x^b
ln(y) = ln(a) + b × ln(x)
```

by least squares on the logarithmic scale for positive paired observations. The application can summarise fitted models for sex/group combinations and the pooled dataset. Confidence intervals and tests require sufficient observations; estimates from very small groups are exploratory and should not be treated as stable biological effects. In particular, a confidence interval for `b` that includes 3 does not establish departure from isometric length–weight scaling.

The built-in analysis is **not** a trained multivariate live-weight prediction model. The weight-derived indices `K`, `PDI`, and `RW` must not be used as predictors of the same observed weight in a supervised-learning benchmark, because this would introduce target leakage.

## Excel output

The full-report export uses these worksheets when the corresponding results are available:

- `Данные_с_индексами` — cleaned records and calculated indices;
- `Сводная_статистика` — overall descriptive statistics;
- `Коэффициенты_регрессии` — fitted allometric parameters;
- `Корреляционная_матрица` — Pearson correlations;
- `Статистика_по_группам` — descriptive statistics by group;
- `Сравнение_групп` — statistical group comparisons;
- `Отброшенные_строки` — excluded records and exclusion reasons.

A separate export option saves only the processed individual records.

## Project structure

```text
Bioanalizator.py            # GUI launcher; also provides --selftest
main.py                     # Alternative launcher and executable entry point
bioanalizator/
    __init__.py             # Package version and metadata
    app.py                  # CustomTkinter desktop interface and exports
    core.py                 # Indices, descriptive statistics and allometric models
    common.py               # Constants, example template, helpers and logging
    tables.py               # Searchable, sortable, paginated tables
assets/
    bioanalizator.ico       # Windows icon
    bioanalizator.png       # Application logo
    logo_source.png         # Logo source
    make_icon.py            # Icon generation utility
    version_info.txt        # Executable version metadata
exe/
    build.ps1               # Windows/PyInstaller build script
    README.md               # Executable-building notes
tests/                      # pytest test suite
requirements.txt            # Runtime dependencies
requirements-dev.txt        # Development/test dependencies
pyproject.toml              # Package metadata
install.bat                 # Windows dependency setup
run.bat                     # Windows launcher
```

## Tests and self-check

Install the test requirements and run the included tests:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

Run the non-interactive dependency and basic-function self-check:

```powershell
python main.py --selftest
```

The self-check exercises sample index and regression calculations, Excel reading/writing, template generation, and figure creation. It writes `selftest_result.txt` in the working directory. It is **not** a reproducibility test of the comparative machine-learning results described in the associated manuscript.

## Build a Windows executable

The archive includes a PowerShell script for PyInstaller:

```powershell
powershell -ExecutionPolicy Bypass -File .\exe\build.ps1
```

Its target output is `exe/dist/Bioanalizator.exe`. The source archive also contains locally generated build intermediates and a compiled executable; these files are **not needed in the source-code repository**. Publish binaries separately as release assets if distribution is required, and keep build caches, logs, `__pycache__`, and local datasets out of version control.

## Reproducibility and research use

This repository documents the **implemented application**, not a complete release of a study's experimental dataset or its comparative predictive-modelling pipeline. To independently reproduce manuscript-level ML metrics, the corresponding dataset or permitted-access procedure, exact predictor list, preprocessing, estimator definitions, train/test indices, tuning and cross-validation scripts, environment specifications, and model outputs would have to be provided separately.

Where the software supports a scientific publication, identify the precise Git commit used for analysis and archive the data-processing protocol. No publication DOI is asserted here.

## License and attribution

The supplied software archive identifies **ВНИИР** as the application author in its package metadata. **No `LICENSE` file is included in the supplied archive.** The availability of source code on GitHub should not be interpreted as permission to reuse, modify, or redistribute it under a particular open-source license; the rights holder should add a verified license before describing the project as open-source.

For questions or corrections, use the repository’s issue tracker where available.
