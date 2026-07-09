"""
app.py — interactive dashboard for Bob's cell-count analysis.

Reuses the analytics functions in analysis.py so nothing is recomputed by hand.
Run locally with:

    streamlit run app.py        (or: make dashboard)

Requires cell_counts.db, which is produced by `python load_data.py`
(or `make pipeline`).
"""

from pathlib import Path

import streamlit as st

import analysis

st.set_page_config(page_title="Cell Count Explorer", layout="wide")

DB_PATH = Path(__file__).resolve().parent / "cell_counts.db"


@st.cache_data
def get_master():
    """Load and cache the joined, percentage-annotated frame."""
    return analysis.load_master()


st.title("Immune Cell Population Explorer")
st.caption("Loblaw Bio clinical trial — cell population frequencies and treatment response")

if not DB_PATH.exists():
    # Self-build on first load (e.g. on Streamlit Cloud, where `make pipeline`
    # is never run). Requires cell-count.csv to be present in the repo.
    import load_data
    try:
        with st.spinner("Building database from cell-count.csv…"):
            load_data.main()
    except FileNotFoundError:
        st.error(
            "Database not found and cell-count.csv is missing, so it cannot be "
            "built. Ensure cell-count.csv is committed to the repository."
        )
        st.stop()

master = get_master()

tab2, tab3, tab4 = st.tabs(
    ["Part 2 — Frequencies", "Part 3 — Responder Comparison", "Part 4 — Baseline Subset"]
)

# ----------------------------------------------------------------------------
# Part 2: relative frequency summary table
# ----------------------------------------------------------------------------
with tab2:
    st.subheader("Relative frequency of each cell population, per sample")
    freq = analysis.frequency_table(master)

    populations = sorted(freq["population"].unique())
    chosen = st.multiselect("Filter populations", populations, default=populations)
    view = freq[freq["population"].isin(chosen)]

    st.dataframe(view, width="stretch", hide_index=True)
    st.caption(
        f"{view['sample'].nunique()} samples · percentages are each population's "
        "share of that sample's total cell count."
    )

# ----------------------------------------------------------------------------
# Part 3: responders vs non-responders (melanoma / miraclib / PBMC)
# ----------------------------------------------------------------------------
with tab3:
    st.subheader("Responders vs non-responders — melanoma, miraclib, PBMC")

    stats = analysis.responder_stats(master)
    fig = analysis.responder_boxplot(master)
    st.pyplot(fig)

    st.markdown("**Mann–Whitney U test per population** (two-sided)")
    st.dataframe(stats, width="stretch", hide_index=True)

    sig = stats.loc[stats["significant_p<0.05"], "population"].tolist()
    if sig:
        st.success(
            "Significant difference (p < 0.05) in relative frequency: "
            + ", ".join(sig)
        )
    else:
        st.info("No population reached p < 0.05.")

# ----------------------------------------------------------------------------
# Part 4: baseline subset breakdowns
# ----------------------------------------------------------------------------
with tab4:
    st.subheader("Baseline samples — melanoma, miraclib, PBMC, time = 0")
    samples, by_project, by_response, by_sex = analysis.baseline_subset(master)

    st.metric("Baseline samples", int(samples["sample"].nunique()))

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Samples per project**")
        st.dataframe(by_project, width="stretch")
    with c2:
        st.markdown("**Subjects by response**")
        st.dataframe(by_response, width="stretch")
    with c3:
        st.markdown("**Subjects by sex**")
        st.dataframe(by_sex, width="stretch")