"""Streamlit dashboard for the ETL Pipeline Monitor."""

import time

import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="ETL Pipeline Monitor", layout="wide")


def fetch(path: str, method: str = "GET") -> dict | list | None:
    """Call the FastAPI backend and return parsed JSON, or None on error."""
    url = f"{API_BASE}{path}"
    try:
        if method == "POST":
            resp = requests.post(url, timeout=10)
        else:
            resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        st.error(f"API error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Page definitions
# ---------------------------------------------------------------------------


def page_dashboard() -> None:
    """Page 1 — Dashboard: pipeline cards with trigger buttons."""
    st.title("ETL Pipeline Monitor")

    pipelines = fetch("/pipelines") or []

    cols = st.columns(len(pipelines) if pipelines else 1)

    for col, pipeline in zip(cols, pipelines):
        name = pipeline.get("name", "unknown")
        status = pipeline.get("last_status") or "never run"
        last_run = pipeline.get("last_run_at") or "—"
        rows = pipeline.get("last_rows_loaded")

        badge_color = "green" if status == "success" else ("red" if status == "failed" else "grey")

        with col:
            st.subheader(name.upper())
            st.markdown(
                f"**Status:** :{badge_color}[{status}]"
            )
            st.markdown(f"**Last run:** {last_run}")
            st.markdown(f"**Rows loaded:** {rows if rows is not None else '—'}")

            if st.button(f"Trigger {name}", key=f"trigger_{name}"):
                result = fetch(f"/pipelines/{name}/trigger", method="POST")
                if result:
                    st.success(result.get("message", "Triggered!"))

    # Auto-refresh every 30 seconds
    time.sleep(30)
    st.rerun()


def page_run_history() -> None:
    """Page 2 — Run History: table of last 20 runs per pipeline."""
    st.title("Run History")

    pipelines_data = fetch("/pipelines") or []
    pipeline_names = [p["name"] for p in pipelines_data]

    if not pipeline_names:
        st.info("No pipelines available.")
        return

    selected = st.selectbox("Select pipeline", pipeline_names)
    runs = fetch(f"/pipelines/{selected}/runs") or []

    if not runs:
        st.info("No runs recorded yet.")
        return

    import pandas as pd

    df = pd.DataFrame(runs)

    # Compute duration
    if "started_at" in df.columns and "finished_at" in df.columns:
        df["duration_s"] = (
            pd.to_datetime(df["finished_at"]) - pd.to_datetime(df["started_at"])
        ).dt.total_seconds()

    # Color failed rows red using pandas Styler
    def highlight_failed(row):
        color = "background-color: #ffcccc" if row.get("status") == "failed" else ""
        return [color] * len(row)

    display_cols = [c for c in ["started_at", "status", "rows_loaded", "duration_s", "s3_key"] if c in df.columns]
    st.dataframe(df[display_cols].style.apply(highlight_failed, axis=1), use_container_width=True)


def page_logs() -> None:
    """Page 3 — Logs: view and trigger logs from the last run."""
    st.title("Pipeline Logs")

    pipelines_data = fetch("/pipelines") or []
    pipeline_names = [p["name"] for p in pipelines_data]

    if not pipeline_names:
        st.info("No pipelines available.")
        return

    selected = st.selectbox("Select pipeline", pipeline_names)

    if st.button("Trigger new run"):
        result = fetch(f"/pipelines/{selected}/trigger", method="POST")
        if result:
            st.success(result.get("message", "Triggered!"))

    logs_data = fetch(f"/pipelines/{selected}/logs")
    logs = logs_data.get("logs", []) if logs_data else []

    if logs:
        st.code("\n".join(logs), language="text")
    else:
        st.info("No logs captured yet. Trigger a run to see logs.")


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

PAGES = {
    "Dashboard": page_dashboard,
    "Run History": page_run_history,
    "Logs": page_logs,
}

page = st.sidebar.radio("Navigation", list(PAGES.keys()))
PAGES[page]()
