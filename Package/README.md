# Reproducibility package

This package contains the data and code needed to reproduce the final 171/44 analysis.

Files:
- `modeling_data_215.csv` - 215-fish modelling data (no PIT-tag or sample-tube identifiers).
- `split.csv` - final 215-fish train/test assignment (171/44).
- `split_initial_217.csv` - original 217-record assignment and the two training exclusions.
- `README_split.md` - description of the two-stage split.
- `retrain_171.py` - main model-comparison workflow (default and tuned models; Figures 5, 6 and S2).
- `repro_common.py` - shared data loading and pipeline helpers.
- `permutation_importance_oof.py` - out-of-fold permutation importance (Table 10 / Table R3.4).
- `reduced_models.py` - full, Reduced A and Reduced B models (Table S3).
- `biometric_indices.py` - group-by-sex biometric indices with K = 100W/FL^3 (Table S2).
- `sensitivity_analysis.py` - 7,250 g and rare-group sensitivity analyses (Tables S4 and S5).
- `allometric_diagnostics.py` - residual/Q-Q plots and Cook's D (Figures S1a/S1b and Table S6).
- `requirements.txt` - Python dependencies.
- `Supplementary_Tables.xlsx` - supplementary Tables S1-S6.
- `figures/` - Figure 5, Figure 6, Supplementary Figures S1a, S1b and S2.

Run:
```
python -m pip install -r requirements.txt
python retrain_171.py
python permutation_importance_oof.py
python reduced_models.py
python biometric_indices.py
python sensitivity_analysis.py
python allometric_diagnostics.py
```

`retrain_171.py` writes results to `retrain_171_outputs/`. The additional scripts write the
corresponding CSV files and supplementary figures to the package directory. The original
217-record assignment was generated with `train_test_split(test_size=0.2, random_state=42,
shuffle=True)` before exclusion of two incomplete training records. No second split was applied
to the 215 complete records.
