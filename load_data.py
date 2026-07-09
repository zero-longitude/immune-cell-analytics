'''
Part 1 - data management

Initializes a normalized SQLite database and loads every row from
cell-count.csv. Run directly, with no arguments:
 
    python load_data.py
 
This (re)creates cell_counts.db in the repository root.
 
Schema (normalized around the project -> subject -> sample -> counts hierarchy):
    subjects(subject_id PK, project, condition, age, sex, treatment, response)
    samples(sample_id PK, subject_id FK, sample_type, time_from_treatment_start)
    cell_counts(sample_id FK, population, count, PK(sample_id, population))
 
The cell_counts table is stored in long ("tidy") format — one row per
sample/population — so adding a new immune population is a data change, not a
schema change, and downstream frequency queries reduce to a simple GROUP BY.
 
Only the Python standard library is used, so loading has no third-party
dependencies.
'''

import csv 
import sqlite3
from pathlib import Path


# Resolves a relative path (./load_data.py) so the script works from any cwd
ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "cell-count.csv"
DB_PATH = ROOT / "cell_counts.db"


# Five types of immune cells
POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]


SCHEMA = """
DROP TABLE IF EXISTS cell_counts;
DROP TABLE IF EXISTS samples;
DROP TABLE IF EXISTS subjects;
 
CREATE TABLE subjects (
    subject_id TEXT PRIMARY KEY,
    project    TEXT,
    condition  TEXT,
    age        INTEGER,
    sex        TEXT,
    treatment  TEXT,
    response   TEXT
);
 
CREATE TABLE samples (
    sample_id                  TEXT PRIMARY KEY,
    subject_id                 TEXT NOT NULL REFERENCES subjects(subject_id),
    sample_type                TEXT,
    time_from_treatment_start  INTEGER
);
 
CREATE TABLE cell_counts (
    sample_id   TEXT NOT NULL REFERENCES samples(sample_id),
    population  TEXT NOT NULL,
    count       INTEGER NOT NULL,
    PRIMARY KEY (sample_id, population)
);
 
-- Indexes on the columns used to filter/join in Parts 2-4.
CREATE INDEX idx_subjects_filters
    ON subjects(condition, treatment, response, sex);
CREATE INDEX idx_samples_subject
    ON samples(subject_id, sample_type, time_from_treatment_start);
"""

def _int_or_none(value):
    """Convert a csv field into an int. Treat a blank as NULL."""
    value = (value or "").strip()
    return int(value) if value else None

def _text_or_none(value):
    """Trim a csv field. Treat blanks as NULL."""
    value = (value or "").strip()
    return value or None


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Expected inout csv at {CSV_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.executescript(SCHEMA)

        with CSV_PATH.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # One subject may appear on many sample rows, the first write wins
                conn.execute(
                    """INSERT OR IGNORE INTO subjects
                       (subject_id, project, condition, age, sex, treatment, response)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row["subject"],
                        _text_or_none(row["project"]),
                        _text_or_none(row["condition"]),
                        _int_or_none(row["age"]),
                        _text_or_none(row["sex"]),
                        _text_or_none(row["treatment"]),
                        _text_or_none(row["response"]),
                    ),
                )
 
                conn.execute(
                    """INSERT INTO samples
                       (sample_id, subject_id, sample_type, time_from_treatment_start)
                       VALUES (?, ?, ?, ?)""",
                    (
                        row["sample"],
                        row["subject"],
                        _text_or_none(row["sample_type"]),
                        _int_or_none(row["time_from_treatment_start"]),
                    ),
                )
 
                conn.executemany(
                    "INSERT INTO cell_counts (sample_id, population, count) VALUES (?, ?, ?)",
                    [(row["sample"], pop, int(row[pop])) for pop in POPULATIONS],
                )
 
        conn.commit()
 
        # Small confirmation 
        n_subjects = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        n_samples = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
        n_counts = conn.execute("SELECT COUNT(*) FROM cell_counts").fetchone()[0]
        print(f"Loaded {n_subjects} subjects, {n_samples} samples, "
              f"{n_counts} cell-count rows into {DB_PATH.name}")
    finally:
        conn.close()
 
 
if __name__ == "__main__":
    main()