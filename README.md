# immune-cell-analytics

SQLite-backed pipeline and interactive dashboard for analyzing immune cell
population frequencies and treatment response from `cell-count.csv`.

## Overview

The project loads per-sample immune cell counts (`b_cell`, `cd8_t_cell`,
`cd4_t_cell`, `nk_cell`, `monocyte`) and associated sample/subject metadata into
a normalized SQLite database, then computes:

- Part 2: relative frequency of each cell population per sample.
- Part 3: comparison of population frequencies between responders and
  non-responders (melanoma, miraclib, PBMC), with a per-population significance
  test and boxplots.
- Part 4: baseline (time = 0) subset breakdowns for the same cohort.

Results are written to `outputs/` and surfaced in a Streamlit dashboard.

## Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt`: `pandas`, `scipy`, `matplotlib`,
  `streamlit`.

## Quickstart

The repository is graded via GitHub Codespaces. All entry points are defined in
the `Makefile`.

```
make setup       # install dependencies from requirements.txt
make pipeline    # build the database (Part 1) and generate outputs (Parts 2-4)
make dashboard   # start the local Streamlit server
```

`make pipeline` runs `load_data.py` then `analysis.py` with no manual
intervention. It creates `cell_counts.db` in the repository root and writes all
tables and plots to `outputs/`.

`make dashboard` runs `streamlit run app.py` and serves the dashboard at
`http://localhost:8501`. If cell_counts.db is not present, the dashboard builds it on first load from cell-count.csv.

## Dashboard

Hosted: [<DASHBOARD_URL>](https://immune-cell-analytics-ukeqhjnxc9pmy9zvk5oyjk.streamlit.app/)

The same application runs locally via `make dashboard`.

## Repository structure

```
.
├── load_data.py         # Part 1: schema definition + CSV load
├── analysis.py          # Parts 2-4: frequency table, statistics, subset queries
├── app.py               # Streamlit dashboard (imports analysis.py)
├── requirements.txt     # dependencies
├── Makefile             # setup / pipeline / dashboard / clean targets
├── cell-count.csv       # input data
├── outputs/             # generated tables and plots
└── README.md
```

Concerns are separated by stage. `load_data.py` handles ingestion and depends
only on the standard library. `analysis.py` handles computation and exposes
functions that return DataFrames and figures. `app.py` handles presentation and
imports those functions directly, so no analytic logic is duplicated between the
pipeline and the dashboard.

## Database schema

Three tables model the project → subject → sample → count hierarchy.

`subjects`
- `subject_id` TEXT PRIMARY KEY
- `project`, `condition`, `sex`, `treatment`, `response` TEXT
- `age` INTEGER

`samples`
- `sample_id` TEXT PRIMARY KEY
- `subject_id` TEXT, foreign key to `subjects(subject_id)`
- `sample_type` TEXT
- `time_from_treatment_start` INTEGER

`cell_counts`
- `sample_id` TEXT, foreign key to `samples(sample_id)`
- `population` TEXT
- `count` INTEGER
- PRIMARY KEY (`sample_id`, `population`)

Indexes are created on the subject-level filter columns
(`condition`, `treatment`, `response`, `sex`) and on the sample-level join and
filter columns (`subject_id`, `sample_type`, `time_from_treatment_start`).

### Rationale

Subject-level attributes (condition, sex, age, treatment, response) are constant
across a subject's samples and are stored once in `subjects` to eliminate the
redundancy present in the flat CSV and to prevent update anomalies. Sample-level
attributes are stored in `samples`. Cell counts are stored in long ("tidy")
format in `cell_counts`, one row per sample/population, rather than as five wide
columns.

### Scaling

The long-format `cell_counts` table means additional immune populations are
inserted as rows and require no schema change; frequency and comparison queries
remain unchanged because they aggregate over `population`. Normalizing
subject-level data keeps storage proportional to the number of distinct subjects
rather than the number of samples. For hundreds of projects and thousands of
samples, the indexed foreign-key columns support the filtering and grouping used
in Parts 3-4 without full table scans. The same relational model transfers to a
client-server engine (e.g. PostgreSQL) without structural change if concurrent
access or larger volumes require it.

## Analysis methods

Part 2. For each sample, `total_count` is the sum of the five population counts.
The relative frequency of a population is `count / total_count * 100`. Output:
`outputs/cell_frequencies.csv` with columns `sample`, `total_count`,
`population`, `count`, `percentage`.

Part 3. The cohort is filtered to `condition = melanoma`, `treatment =
miraclib`, `sample_type = PBMC`, with `response` in {yes, no}. For each
population, responder and non-responder relative frequencies are compared with a
two-sided Mann–Whitney U test (`scipy.stats.mannwhitneyu`), a non-parametric
test that does not assume normally distributed frequencies. Populations with
p < 0.05 are reported as significant. Output: `outputs/responder_stats.csv` and
`outputs/responder_boxplot.png`. The comparison is performed at the sample level
across all PBMC timepoints, as specified; samples from the same subject at
different timepoints are not treated as independent, which should be considered
when interpreting the p-values.

Part 4. The cohort above is further restricted to `time_from_treatment_start =
0`. The subset is summarized by sample count per project and by distinct-subject
counts per response value and per sex. Output: `outputs/subset_summary.csv`.

## Outputs

- `outputs/cell_frequencies.csv` — Part 2 relative frequency table.
- `outputs/responder_stats.csv` — Part 3 per-population test results.
- `outputs/responder_boxplot.png` — Part 3 boxplots.
- `outputs/subset_summary.csv` — Part 4 baseline breakdowns.
