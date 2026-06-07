from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from database import (
    create_topic,
    delete_topic,
    export_backup,
    fetch_topic,
    get_all_topics,
    initialize_db,
    import_json,
    record_review,
    update_topic,
)


def sanitize_text(value: str) -> str:
    """Trim whitespace and normalize a text field."""
    return value.strip()


def ensure_session_state() -> None:
    if "editing_topic_id" not in st.session_state:
        st.session_state.editing_topic_id = None
    if "random_topic_id" not in st.session_state:
        st.session_state.random_topic_id = None


def render_sidebar() -> None:
    st.sidebar.title("Manage Topics")
    st.sidebar.markdown("### Add Subject / Topic")

    subject_name = st.sidebar.text_input("Subject name", key="sidebar_subject")
    topic_name = st.sidebar.text_input("Topic name", key="sidebar_topic")

    if st.sidebar.button("Add Topic"):
        subject_name = sanitize_text(subject_name)
        topic_name = sanitize_text(topic_name)
        if not subject_name or not topic_name:
            st.sidebar.error("Subject and topic cannot be empty.")
        else:
            try:
                create_topic(subject_name, topic_name)
                st.sidebar.success("Topic added successfully.")
                st.experimental_rerun()
            except sqlite3.IntegrityError:
                st.sidebar.error("That subject/topic already exists.")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Import / Export")

    uploaded_file = st.sidebar.file_uploader("Upload JSON backup", type=["json"])
    if st.sidebar.button("Import JSON"):
        if uploaded_file is None:
            st.sidebar.warning("Choose a JSON file first.")
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_path = Path(temp_file.name)

            try:
                inserted, skipped = import_json(str(temp_path))
                st.sidebar.success(f"Imported {inserted} topics. Skipped {skipped} duplicates.")
                st.experimental_rerun()
            except ValueError as exc:
                st.sidebar.error(f"Invalid JSON format: {exc}")
            finally:
                if temp_path.exists():
                    temp_path.unlink()

    backup_json = export_backup()
    st.sidebar.download_button(
        label="Export Backup",
        data=backup_json,
        file_name="study_helper_backup.json",
        mime="application/json",
    )


def render_statistics(topics: list[dict[str, Any]]) -> None:
    total_topics = len(topics)
    reviewed = sum(1 for topic in topics if topic["review_count"] > 0)
    never_reviewed = total_topics - reviewed
    average_confidence = round(
        float(sum(topic["confidence"] for topic in topics) / total_topics) if total_topics else 0.0,
        2,
    )

    stats_columns = st.columns(4)
    stats_columns[0].metric("Total topics", total_topics)
    stats_columns[1].metric("Reviewed at least once", reviewed)
    stats_columns[2].metric("Never reviewed", never_reviewed)
    stats_columns[3].metric("Average confidence", average_confidence)


def render_topic_management(topics: list[dict[str, Any]]) -> None:
    st.subheader("Topic Management")

    if not topics:
        st.info("No topics yet. Use the sidebar to add your first subject and topic.")
        return

    table_data = pd.DataFrame(topics)
    table_data = table_data.rename(
        columns={
            "subject": "Subject",
            "topic": "Topic",
            "review_count": "Reviews",
            "confidence": "Confidence",
            "last_reviewed": "Last reviewed",
        }
    )
    table_data["Last reviewed"] = table_data["Last reviewed"].fillna("Never")
    st.dataframe(table_data[["Subject", "Topic", "Reviews", "Confidence", "Last reviewed"]], use_container_width=True)

    st.markdown("---")
    st.write("Use the controls below to edit or delete a topic.")

    for topic in topics:
        columns = st.columns([2, 4, 1, 1, 1, 1])
        columns[0].write(topic["subject"])
        columns[1].write(topic["topic"])
        columns[2].write(topic["review_count"])
        columns[3].write(topic["confidence"])
        columns[4].write(topic["last_reviewed"] or "Never")

        if columns[5].button("Edit", key=f"edit_{topic['id']}"):
            st.session_state.editing_topic_id = topic["id"]

        if st.session_state.editing_topic_id == topic["id"]:
            with st.expander("Edit topic", expanded=True):
                edited_subject = st.text_input(
                    "Subject",
                    value=topic["subject"],
                    key=f"edit_subject_{topic['id']}",
                )
                edited_topic = st.text_input(
                    "Topic",
                    value=topic["topic"],
                    key=f"edit_topic_{topic['id']}",
                )
                save_button = st.button("Save changes", key=f"save_{topic['id']}")
                cancel_button = st.button("Cancel", key=f"cancel_{topic['id']}")

                if cancel_button:
                    st.session_state.editing_topic_id = None
                    st.experimental_rerun()

                if save_button:
                    edited_subject = sanitize_text(edited_subject)
                    edited_topic = sanitize_text(edited_topic)
                    if not edited_subject or not edited_topic:
                        st.error("Subject and topic cannot be empty.")
                    else:
                        try:
                            update_topic(topic["id"], edited_subject, edited_topic)
                            st.success("Topic updated successfully.")
                            st.session_state.editing_topic_id = None
                            st.experimental_rerun()
                        except sqlite3.IntegrityError:
                            st.error("A topic with that subject and topic already exists.")

        if columns[5].button("Delete", key=f"delete_{topic['id']}"):
            delete_topic(topic["id"])
            st.success("Topic deleted.")
            if st.session_state.editing_topic_id == topic["id"]:
                st.session_state.editing_topic_id = None
            st.experimental_rerun()


def render_random_revision() -> None:
    st.subheader("Random Revision")

    if st.button("Generate Random Topic"):
        random_topic = fetch_random_topic()
        if random_topic is None:
            st.warning("Add a topic first to generate a revision item.")
        else:
            st.session_state.random_topic_id = random_topic["id"]
            st.experimental_rerun()

    if st.session_state.random_topic_id is None:
        st.info("Generate a random topic to begin revision.")
        return

    topic = fetch_topic(st.session_state.random_topic_id)
    if topic is None:
        st.warning("The selected topic is no longer available.")
        st.session_state.random_topic_id = None
        return

    st.markdown(f"**Subject:** {topic['subject']}  \n**Topic:** {topic['topic']}")
    st.write(f"Reviews: {topic['review_count']} — Confidence: {topic['confidence']}")
    st.write(f"Last reviewed: {topic['last_reviewed'] or 'Never'}")

    columns = st.columns(3)
    if columns[0].button("Easy"):
        record_review(topic["id"], "easy")
        st.success("Review saved: easy.")
        st.experimental_rerun()

    if columns[1].button("Medium"):
        record_review(topic["id"], "medium")
        st.success("Review saved: medium.")
        st.experimental_rerun()

    if columns[2].button("Hard"):
        record_review(topic["id"], "hard")
        st.success("Review saved: hard.")
        st.experimental_rerun()


def fetch_random_topic() -> dict[str, Any] | None:
    topics = get_all_topics()
    if not topics:
        return None

    weights = [max(1, 5 - topic["confidence"]) for topic in topics]
    candidates = pd.DataFrame(topics)
    selected = candidates.sample(weights=weights, n=1, random_state=None).iloc[0]
    return selected.to_dict()


def render_progress_dashboard(topics: list[dict[str, Any]]) -> None:
    st.subheader("Progress Dashboard")

    if not topics:
        st.info("Add topics to see progress charts and completion metrics.")
        return

    df = pd.DataFrame(topics)
    df["completed"] = df["review_count"] > 0
    summary = (
        df.groupby("subject", sort=False)
        .agg(
            total_topics=("id", "count"),
            completed_topics=("completed", "sum"),
        )
        .reset_index()
    )
    summary["completion_pct"] = (summary["completed_topics"] / summary["total_topics"] * 100).round(1)
    summary = summary.sort_values(by="completion_pct", ascending=False)

    chart, table = st.columns([1, 1])
    with chart:
        fig = px.pie(
            summary,
            names="subject",
            values="completed_topics",
            hole=0.45,
            title="Completed Topics by Subject",
            labels={"subject": "Subject", "completed_topics": "Completed"},
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    with table:
        display_table = summary.rename(
            columns={
                "subject": "Subject",
                "total_topics": "Total Topics",
                "completed_topics": "Completed Topics",
                "completion_pct": "Completion %",
            }
        )
        st.dataframe(display_table, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Study Helper", layout="wide")
    initialize_db()
    ensure_session_state()

    st.title("📚 Study Helper")
    st.markdown(
        "A lightweight revision assistant for medical oral exams. Add topics, review them repeatedly, and track progress visually."
    )

    render_sidebar()

    topics = get_all_topics()

    render_statistics(topics)

    with st.expander("Topic Management", expanded=True):
        render_topic_management(topics)

    with st.expander("Random Revision", expanded=True):
        render_random_revision()

    with st.expander("Progress Dashboard", expanded=True):
        render_progress_dashboard(topics)


if __name__ == "__main__":
    main()
