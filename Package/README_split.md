# Train/test split and eligibility filtering

`split_initial_217.csv` documents the original 217 candidate records and the initial random
hold-out assignment. `split.csv` contains the final 215-fish analysis sample.

Procedure:
1. The initial source table contained 217 records.
2. A single random 80/20 hold-out was generated before eligibility filtering with
   scikit-learn `train_test_split(test_size=0.2, random_state=42, shuffle=True)`,
   producing 173 training and 44 test records.
3. Two training records were excluded because one lacked the breeding-group label
   (ID 27) and the other lacked the sex annotation (ID 3). No test records were
   removed or reassigned.
4. The final modelling dataset therefore contains 171 training and 44 test fish
   (n = 215; 79.53%/20.47%). No second 80/20 split was performed on the 215
   complete records.

`split_initial_217.csv` columns:
- `ID` — internal fish identifier;
- `Breeding_group` — breeding group;
- `Sex` — Female / Male / Not recorded;
- `Live_weight_g` — live weight in grams;
- `Split_initial` — original Train / Test assignment;
- `Included_final` — Yes / No for the 215-fish analysis;
- `Exclusion_reason` — reason for exclusion, where applicable.

`split.csv` contains the final 215 records with `Split` = Train / Test.
The files contain no PIT-tag or sample-tube numbers; `ID` is an internal identifier only.
