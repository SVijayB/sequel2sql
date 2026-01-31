"""Streamlit dashboard to visualize baseline_gemini_final_output.jsonl.

Run from project root:
  streamlit run src/evaluation/baseline_dashboard.py

Select an instance to view query, intent, issue SQL, then pred_sql vs sol_sql side-by-side.
"""

import json
from pathlib import Path

import streamlit as st


def load_baseline_jsonl(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sql_list_to_display(sql_list: list) -> str:
    if not sql_list:
        return "(empty)"
    if isinstance(sql_list, list):
        return "\n\n".join(str(s).strip() for s in sql_list if s)
    return str(sql_list).strip()


def main() -> None:
    st.set_page_config(page_title="Baseline results", layout="wide")
    st.title("Baseline results viewer")
    st.caption("Compare predicted SQL vs gold solution per instance")

    # Resolve data path (works when run as script or as module)
    try:
        from .config import load_config
        config = load_config()
        data_path = Path(config.get_output_path("data", "results", "baseline_gemini_final_output.jsonl"))
    except Exception:
        base = Path(__file__).resolve().parent.parent.parent
        data_path = base / "evaluation_output" / "data" / "results" / "baseline_gemini_final_output.jsonl"
        if not data_path.exists():
            data_path = Path("evaluation_output/data/results/baseline_gemini_final_output.jsonl")

    if not data_path.exists():
        st.error(f"File not found: {data_path}. Run the baseline first.")
        return

    data = load_baseline_jsonl(data_path)
    options = [r["instance_id"] for r in data]
    index_map = {r["instance_id"]: i for i, r in enumerate(data)}

    selected_id = st.selectbox(
        "Select instance",
        options=options,
        index=0,
        help="Choose which query/instance to inspect",
    )
    idx = index_map[selected_id]
    row = data[idx]

    # Meta
    st.subheader("Instance")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Instance ID", row.get("instance_id", ""))
    with c2:
        st.metric("Database", row.get("db_id", ""))
    with c3:
        st.metric("Dialect", row.get("dialect", "") + " " + str(row.get("version", "")))

    # Query (intent)
    st.subheader("Query / intent")
    st.write(row.get("query", "(no query)"))

    # Buggy SQL
    st.subheader("Issue SQL (buggy)")
    issue_sql = sql_list_to_display(row.get("issue_sql", []))
    st.code(issue_sql, language="sql")

    # Pred vs Sol — one below the other, clearly labeled
    st.subheader("Predicted vs solution")
    pred_sql = sql_list_to_display(row.get("pred_sqls", []))
    sol_sql = sql_list_to_display(row.get("sol_sql", []))

    st.markdown("**Predicted SQL** (model output)")
    st.code(pred_sql, language="sql")

    st.markdown("**Solution SQL** (gold)")
    st.code(sol_sql, language="sql")

    # Optional: preprocess / clean_up / test_cases in expanders
    with st.expander("Preprocess SQL"):
        pre = sql_list_to_display(row.get("preprocess_sql", []))
        st.code(pre if pre != "(empty)" else "# none", language="sql")

    with st.expander("Clean-up SQL"):
        clean = sql_list_to_display(row.get("clean_up_sql", []))
        st.code(clean if clean != "(empty)" else "# none", language="sql")

    with st.expander("Test cases (Python)"):
        tc = row.get("test_cases", [])
        if tc:
            st.code("\n".join(str(t).strip() for t in tc), language="python")
        else:
            st.write("(none)")

    # Footer
    st.divider()
    st.caption(f"Loaded {len(data)} instances from {data_path}")


if __name__ == "__main__":
    main()
