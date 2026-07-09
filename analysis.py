"""
analysis.py — analytics over cell_counts.db

Reads the SQLite database produced by load_data.py and generates every
required output. Run directly, with no arguments:

    python analysis.py

Writes to outputs/:
    cell_frequencies.csv   Part 2 - per-sample relative frequencies
    responder_stats.csv    Part 3 - Mann-Whitney U results per population
    responder_boxplot.png  Part 3 - responder vs non-responder boxplots
    subset_summary.csv     Part 4 - baseline subset breakdowns

The functions below return DataFrames/figures so the Streamlit dashboard
(app.py) can reuse them without recomputation.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend so the pipeline runs without a display
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cell_counts.db"
OUTPUT_DIR = ROOT / "outputs"

POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]

# Cohort of interest for Parts 3 & 4: melanoma patients on miraclib, PBMC only.
COHORT = "condition == 'melanoma' and treatment == 'miraclib' and sample_type == 'PBMC'"


def load_master(db_path=DB_PATH):
    """Join all three tables into one tidy frame (one row per sample/population)
    and attach total_count and percentage (relative frequency)."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT c.sample_id      AS sample,
                   c.population      AS population,
                   c.count           AS count,
                   s.subject_id      AS subject,
                   s.sample_type     AS sample_type,
                   s.time_from_treatment_start AS time_from_treatment_start,
                   sub.project       AS project,
                   sub.condition     AS condition,
                   sub.treatment     AS treatment,
                   sub.response      AS response,
                   sub.sex           AS sex
            FROM cell_counts c
            JOIN samples  s   ON c.sample_id  = s.sample_id
            JOIN subjects sub ON s.subject_id = sub.subject_id
            """,
            conn,
        )
    finally:
        conn.close()

    totals = df.groupby("sample")["count"].transform("sum")
    df["total_count"] = totals
    df["percentage"] = df["count"] / df["total_count"] * 100
    return df


def frequency_table(master):
    """Part 2: summary table of relative frequency per sample/population."""
    return (
        master[["sample", "total_count", "population", "count", "percentage"]]
        .sort_values(["sample", "population"])
        .reset_index(drop=True)
    )


def responder_stats(master):
    """Part 3: Mann-Whitney U test per population, responders vs non-responders,
    within the melanoma/miraclib/PBMC cohort. Returns a results DataFrame."""
    cohort = master.query(COHORT)
    cohort = cohort[cohort["response"].isin(["yes", "no"])]

    rows = []
    for pop in POPULATIONS:
        pop_df = cohort[cohort["population"] == pop]
        responders = pop_df.loc[pop_df["response"] == "yes", "percentage"]
        non_responders = pop_df.loc[pop_df["response"] == "no", "percentage"]
        if len(responders) == 0 or len(non_responders) == 0:
            continue
        # Two-sided, non-parametric: no normality assumption on frequencies.
        stat, p = mannwhitneyu(responders, non_responders, alternative="two-sided")
        rows.append({
            "population": pop,
            "n_responders": len(responders),
            "n_non_responders": len(non_responders),
            "median_responder_pct": round(responders.median(), 3),
            "median_non_responder_pct": round(non_responders.median(), 3),
            "u_statistic": round(stat, 1),
            "p_value": round(p, 4),
            "significant_p<0.05": p < 0.05,
        })
    return pd.DataFrame(rows)


def responder_boxplot(master):
    """Part 3: boxplot of relative frequency by population, split responder vs
    non-responder. Returns a matplotlib Figure."""
    cohort = master.query(COHORT)
    cohort = cohort[cohort["response"].isin(["yes", "no"])]

    fig, axes = plt.subplots(1, len(POPULATIONS), figsize=(4 * len(POPULATIONS), 5), sharey=False)
    for ax, pop in zip(axes, POPULATIONS):
        pop_df = cohort[cohort["population"] == pop]
        data = [
            pop_df.loc[pop_df["response"] == "yes", "percentage"].values,
            pop_df.loc[pop_df["response"] == "no", "percentage"].values,
        ]
        ax.boxplot(data)
        ax.set_xticks([1, 2])
        ax.set_xticklabels(["responder", "non-responder"])
        ax.set_title(pop)
        ax.set_ylabel("relative frequency (%)")
        ax.tick_params(axis="x", rotation=15)
    fig.suptitle("Melanoma / miraclib / PBMC: responders vs non-responders")
    fig.tight_layout()
    return fig


def baseline_subset(master):
    """Part 4: baseline (time=0) melanoma/miraclib/PBMC samples, with breakdowns
    by project (samples), and by response and sex (distinct subjects)."""
    subset = master.query(COHORT + " and time_from_treatment_start == 0")

    # Collapse to one row per sample (population rows are redundant here).
    samples = subset.drop_duplicates(subset="sample")

    by_project = samples.groupby("project")["sample"].nunique().rename("n_samples")
    # Response and sex are subject-level, so count distinct subjects.
    subjects = samples.drop_duplicates(subset="subject")
    by_response = subjects.groupby("response")["subject"].nunique().rename("n_subjects")
    by_sex = subjects.groupby("sex")["subject"].nunique().rename("n_subjects")

    return samples, by_project, by_response, by_sex


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH.name} not found. Run `python load_data.py` first."
        )
    OUTPUT_DIR.mkdir(exist_ok=True)
    master = load_master()

    # Part 2
    freq = frequency_table(master)
    freq.to_csv(OUTPUT_DIR / "cell_frequencies.csv", index=False)

    # Part 3
    stats = responder_stats(master)
    stats.to_csv(OUTPUT_DIR / "responder_stats.csv", index=False)
    fig = responder_boxplot(master)
    fig.savefig(OUTPUT_DIR / "responder_boxplot.png", dpi=120)
    plt.close(fig)

    # Part 4
    samples, by_project, by_response, by_sex = baseline_subset(master)
    with (OUTPUT_DIR / "subset_summary.csv").open("w") as f:
        f.write("# Baseline melanoma/miraclib/PBMC samples (time_from_treatment_start = 0)\n")
        f.write(f"# total baseline samples,{samples['sample'].nunique()}\n\n")
        f.write("samples_by_project\n")
        by_project.to_csv(f)
        f.write("\nsubjects_by_response\n")
        by_response.to_csv(f)
        f.write("\nsubjects_by_sex\n")
        by_sex.to_csv(f)

    # Console summary
    print("Part 2: wrote cell_frequencies.csv "
          f"({len(freq)} rows, {freq['sample'].nunique()} samples)")
    print("Part 3: significant populations (p<0.05): "
          f"{stats.loc[stats['significant_p<0.05'], 'population'].tolist()}")
    print(f"Part 4: {samples['sample'].nunique()} baseline samples")
    print("  by project:", by_project.to_dict())
    print("  by response:", by_response.to_dict())
    print("  by sex:", by_sex.to_dict())


if __name__ == "__main__":
    main()