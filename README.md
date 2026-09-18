# Biometric Analysis Tool for Common Carp

This repository contains the Python-based biometric analysis software associated with the manuscript:

**“Morphometric Live-Weight Prediction in Common Carp Breeding Populations: A Python-Based Biometric Tool with Comparative Machine-Learning Models”**

The manuscript is prepared for submission to the MDPI journal **Fishes**.

## Overview

The software was developed to support reproducible processing and analysis of morphometric records collected from breeding populations of common carp (*Cyprinus carpio*). The graphical application integrates data import, column mapping, calculation of biometric indices, descriptive statistics, length–weight allometric modelling, visualization, and export of analytical results.

The current repository provides the source code of the desktop biometric-analysis tool used in the study.

## Main Features

- Import morphometric data from Excel files (`.xlsx`, `.xls`);
- Manual mapping of spreadsheet columns to analytical variables;
- Calculation of biometric indices, including:
  - Fulton condition factor;
  - physical development index;
  - relative weight;
  - relative head-length (cephalic) index;
  - body-shape/elongation index;
- Length–weight allometric regression;
- Group- and sex-specific summaries where the required variables are available;
- Interactive visualization of morphometric relationships;
- Export of processed data, summary statistics, and regression results to Excel;
- Graphical user interface based on `customtkinter`.

## Repository Contents

```text
.
├── biometric_analysis_tool.py   # Main desktop application
└── README.md                    # Repository documentation
```

Additional reproducibility files may be added to the repository together with the final manuscript version.

## Requirements

The application requires Python 3 and the following packages:

```text
customtkinter
pandas
numpy
matplotlib
openpyxl
```

`tkinter` is also required and is included with many standard Python installations.

## Installation

Clone the repository:

```bash
git clone <REPOSITORY_URL>
cd <REPOSITORY_NAME>
```

Install the required Python packages:

```bash
pip install customtkinter pandas numpy matplotlib openpyxl
```

## Running the Application

Run:

```bash
python biometric_analysis_tool.py
```

The graphical interface will open and allow the user to load an Excel file, map data columns, calculate biometric indices, generate plots, and export results.

## Input Data

At minimum, the program requires columns corresponding to:

- live weight, g;
- fork/commercial length, cm.

Optional variables supported by the interface include:

- sample number;
- PIT-chip number;
- sample-tube identifier;
- total/standard length;
- head length;
- body girth;
- maximum body height;
- dorsal-fin ray count;
- anal-fin ray count;
- sex;
- age;
- breeding group or other notes.

Column names can be mapped manually in the graphical interface, so the source spreadsheet does not need to use fixed English column names.

## Output

The application can generate and export:

- individual biometric indices;
- summary statistics;
- allometric regression coefficients;
- graphical visualizations;
- processed Excel workbooks.

## Associated Study

The software accompanies the manuscript:

> **Morphometric Live-Weight Prediction in Common Carp Breeding Populations: A Python-Based Biometric Tool with Comparative Machine-Learning Models**

The study investigates morphometric live-weight prediction in breeding populations of common carp and evaluates the use of reproducible computational tools for routine biometric analysis and selection-oriented data processing.

## Reproducibility

For reproducible use, the repository should be cited together with the final published article. A versioned release and permanent repository identifier/DOI can be added after manuscript acceptance or publication.

## Citation

If you use this software, please cite the associated article after publication. The complete bibliographic citation and DOI will be added here once available.

```text
[Article citation and DOI to be added after publication]
```

## Contact

For questions regarding the software or the associated manuscript, please contact the corresponding author through the contact information provided in the manuscript.
