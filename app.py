from __future__ import annotations

import random
import sqlite3
import tempfile
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


def render_styles() -> None:
    st.markdown(
        """
        <style>
        /* Dark / black theme */
        body, .stApp {
            background: #0b1220;
            color: #e6eef8;
        }

        .css-18e3th9,
        .css-1d391kg,
        .css-1v0mbdj,
        .css-1lcbmhc {
            background: #071021;
            color: #e6eef8;
        }

        .stSidebar {
            background-color: #071021;
            color: #e6eef8;
        }

        .stButton button,
        .stDownloadButton button {
            background-color: #7c3aed !important;
            color: white !important;
            border-radius: 8px !important;
            border: none !important;
        }

        h1, h2, h3, h4, h5, h6 {
            color: #e6eef8;
        }

        .stMetricValue {
            color: #f8fafc !important;
        }

        .stAlert {
            border-radius: 10px;
            background: rgba(255,255,255,0.04);
            color: #e6eef8;
        }

        .css-1v0mbdj .st-c4 {
            color: #e6eef8;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sanitize_text(value: str) -> str:
    return value.strip()


def ensure_session_state() -> None:
    if "editing_topic_id" not in st.session_state:
        st.session_state.editing_topic_id = None
    if "random_topic_id" not in st.session_state:
        st.session_state.random_topic_id = None
    if "selected_topic_id" not in st.session_state:
        st.session_state.selected_topic_id = None
    if "sidebar_topic" not in st.session_state:
        st.session_state.sidebar_topic = ""
    if "sidebar_message" not in st.session_state:
        st.session_state.sidebar_message = ""
    if "sidebar_error" not in st.session_state:
        st.session_state.sidebar_error = ""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Home"


def handle_add_topic() -> None:
    topic_name = sanitize_text(st.session_state.sidebar_topic)
    if not topic_name:
        st.session_state.sidebar_error = "Topic cannot be empty."
        st.session_state.sidebar_message = ""
        return

    try:
        create_topic("General", topic_name)
        st.session_state.sidebar_topic = ""
        st.session_state.sidebar_message = "Topic added successfully."
        st.session_state.sidebar_error = ""
    except sqlite3.IntegrityError:
        st.session_state.sidebar_error = "That topic already exists."
        st.session_state.sidebar_message = ""


def handle_import_json() -> None:
    uploaded_file = st.session_state.upload_json_file
    if uploaded_file is None:
        st.session_state.sidebar_error = "Choose a JSON file first."
        st.session_state.sidebar_message = ""
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
        temp_file.write(uploaded_file.getvalue())
        temp_path = Path(temp_file.name)

    try:
        inserted, skipped = import_json(str(temp_path))
        st.session_state.sidebar_message = f"Imported {inserted} topics. Skipped {skipped} duplicates."
        st.session_state.sidebar_error = ""
    except ValueError as exc:
        st.session_state.sidebar_error = f"Invalid JSON format: {exc}"
        st.session_state.sidebar_message = ""
    finally:
        if temp_path.exists():
            temp_path.unlink()


def handle_mark_review(topic_id: int) -> None:
    """Mark the topic as reviewed (simple flow).

    Uses the existing `record_review` logic with an "easy" outcome
    so review_count and confidence are updated and persisted.
    """
    try:
        record_review(topic_id, "easy")
        st.session_state.sidebar_message = "Review saved."
    except Exception:
        st.session_state.sidebar_error = "Failed to record review."
    # Clear the currently shown random topic so user can generate a new one
    st.session_state.random_topic_id = None


def render_sidebar() -> None:
    st.sidebar.title("Study Helper")
    st.sidebar.markdown("### Navigation")
    st.sidebar.radio("Choose a page", ["Home", "Topic Management"], key="current_page")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Add Topic")
    st.sidebar.text_input("Topic name", key="sidebar_topic")
    st.sidebar.button("Add Topic", on_click=handle_add_topic)

    if st.session_state.sidebar_error:
        st.sidebar.error(st.session_state.sidebar_error)
    elif st.session_state.sidebar_message:
        st.sidebar.success(st.session_state.sidebar_message)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Import / Export")
    st.sidebar.file_uploader("Upload JSON backup", type=["json"], key="upload_json_file")
    st.sidebar.button("Import JSON", on_click=handle_import_json)

    if st.session_state.sidebar_error:
        st.sidebar.error(st.session_state.sidebar_error)
    elif st.session_state.sidebar_message:
        st.sidebar.success(st.session_state.sidebar_message)

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
        st.info("No topics yet. Use the sidebar to add your first topic.")
        return

    table_data = pd.DataFrame(topics)
    table_data = table_data.rename(
        columns={
            "topic": "Topic",
            "review_count": "Reviews",
            "confidence": "Confidence",
            "last_reviewed": "Last reviewed",
        }
    )
    table_data["Last reviewed"] = table_data["Last reviewed"].fillna("Never")
    st.dataframe(table_data[["Topic", "Reviews", "Confidence", "Last reviewed"]], use_container_width=True)

    st.markdown("---")
    st.write("Use the controls below to edit or delete a topic.")

    for topic in topics:
        cols = st.columns([8, 1, 1])
        cols[0].write(topic["topic"])

        if cols[1].button("Edit", key=f"edit_{topic['id']}"):
            st.session_state.editing_topic_id = topic["id"]

        if st.session_state.editing_topic_id == topic["id"]:
            with st.expander("Edit topic", expanded=True):
                edited_topic = st.text_input(
                    "Topic",
                    value=topic["topic"],
                    key=f"edit_topic_{topic['id']}",
                )
                save_button = st.button("Save changes", key=f"save_{topic['id']}")
                cancel_button = st.button("Cancel", key=f"cancel_{topic['id']}")

                if cancel_button:
                    st.session_state.editing_topic_id = None

                if save_button:
                    edited_topic = sanitize_text(edited_topic)
                    if not edited_topic:
                        st.error("Topic cannot be empty.")
                    else:
                        try:
                            update_topic(topic["id"], topic.get("subject", "General"), edited_topic)
                            st.success("Topic updated successfully.")
                            st.session_state.editing_topic_id = None
                        except sqlite3.IntegrityError:
                            st.error("A topic with that name already exists.")

        if cols[2].button("Delete", key=f"delete_{topic['id']}"):
            delete_topic(topic["id"])
            st.success("Topic deleted.")
            if st.session_state.editing_topic_id == topic["id"]:
                st.session_state.editing_topic_id = None


def render_random_revision(topics: list[dict[str, Any]]) -> None:
    st.subheader("Random Revision")
    st.markdown("Choose a random topic or pick one manually to review.")

    if topics:
        topic_options = {topic["id"]: topic["topic"] for topic in topics}
        selected_topic_id = st.selectbox(
            "Choose a topic to review",
            options=list(topic_options.keys()),
            format_func=lambda topic_id: topic_options[topic_id],
            key="selected_topic_id",
        )

        if st.button("Review selected topic", on_click=handle_mark_review, args=(selected_topic_id,)):
            pass
    else:
        selected_topic_id = None

    st.markdown("---")
    if st.button("Generate Random Topic"):
        random_topic = fetch_random_topic()
        if random_topic is None:
            st.warning("Add a topic first to generate a revision item.")
        else:
            st.session_state.random_topic_id = random_topic["id"]

    if selected_topic_id is None and st.session_state.random_topic_id is None:
        st.info("Generate a random topic or select one to begin revision.")
        return

    if selected_topic_id is not None:
        topic = fetch_topic(selected_topic_id)
    else:
        topic = fetch_topic(st.session_state.random_topic_id)

    if topic is None:
        st.warning("The selected topic is no longer available.")
        st.session_state.random_topic_id = None
        st.session_state.selected_topic_id = None
        return

    # Prominent, colorful topic display
    card_html = f"""
    <div style="background: linear-gradient(90deg,#071021,#0b1220); padding:36px; border-radius:14px; text-align:center;">
      <div style="font-size:36px; color:#f0abfc; font-weight:800;">{topic['topic']}</div>
      <div style="margin-top:10px; color:#c7d2fe;">Reviews: {topic['review_count']} &nbsp; • &nbsp; Confidence: {topic['confidence']}</div>
      <div style="margin-top:6px; color:#94a3b8; font-size:13px;">Last reviewed: {topic['last_reviewed'] or 'Never'}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    if st.button("Mark Reviewed", on_click=handle_mark_review, args=(topic["id"],)):
        pass


def fetch_random_topic() -> dict[str, Any] | None:
    topics = get_all_topics()
    if not topics:
        return None

    weights = [max(1, 5 - topic["confidence"]) for topic in topics]
    return random.choices(topics, weights=weights, k=1)[0]


def render_progress_dashboard(topics: list[dict[str, Any]]) -> None:
    st.subheader("Progress Dashboard")

    if not topics:
        st.info("Add topics to see progress charts and completion metrics.")
        return

    total_topics = len(topics)
    completed = sum(1 for topic in topics if topic["review_count"] > 0)
    remaining = total_topics - completed
    completion_pct = round((completed / total_topics) * 100, 1) if total_topics else 0.0

    chart_col, info_col = st.columns([2, 1])
    with chart_col:
        fig = px.pie(
            names=["Completed", "Remaining"],
            values=[completed, remaining],
            hole=0.5,
            title="Completed Topics",
            color_discrete_map={"Completed": "#10b981", "Remaining": "#93c5fd"},
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    with info_col:
        st.metric("Completion rate", f"{completion_pct}%")
        st.write(f"**Completed:** {completed}")
        st.write(f"**Remaining:** {remaining}")
        st.progress(completed / total_topics)


def main() -> None:
    st.set_page_config(page_title="Study Helper", layout="wide")
    initialize_db()
    ensure_session_state()
    render_styles()

    st.title("📚 Study Helper")
    st.markdown(
        "A clean, topic-focused study helper for oral exam revision. Add topics, review them randomly, and track your progress visually."
    )

    render_sidebar()

    topics = get_all_topics()
    page = st.session_state.current_page

    if page == "Topic Management":
        render_topic_management(topics)
    else:
        render_statistics(topics)
        st.markdown("---")
        render_random_revision(topics)
        st.markdown("---")
        render_progress_dashboard(topics)


if __name__ == "__main__":
    main()
