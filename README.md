# Study Helper

A Streamlit application to help medical students organize exam topics, review them randomly with weighted difficulty, track progress by subject, and persist all data using SQLite.

## Features

- Add subjects and topics from the UI
- Edit and delete existing topics
- Generate a random revision topic with weighted selection based on confidence
- Mark topics as reviewed with Easy / Medium / Hard outcomes
- Track progress with Plotly doughnut charts and completion tables
- Import existing JSON backup files
- Export a JSON backup directly from the browser
- Persist all data in a local SQLite database (`study.db`)

## Installation

1. Create a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Running locally

From the project root:

```bash
streamlit run app.py
```

The application will open in your browser and automatically create `study.db` on first run.

## Database

The application uses SQLite and stores data in `study.db`.

The table schema is:

- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `subject` TEXT NOT NULL
- `topic` TEXT NOT NULL
- `review_count` INTEGER DEFAULT 0
- `confidence` INTEGER DEFAULT 0
- `last_reviewed` DATETIME NULL
- `created_at` DATETIME

The database is created automatically by `database.py`.

## Deployment on Streamlit Community Cloud

1. Push the repository to GitHub.
2. Open Streamlit Community Cloud and create a new app.
3. Connect the GitHub repository and select the `main` branch.
4. Set the main file path to `app.py`.
5. Deploy.

> `study.db` is created automatically on deployment. For long-term backup, use the built-in `Export Backup` button.

## Notes

- Do not use external APIs.
- The JSON import/export format matches the expected structure with `subjects` and `subtopics`.
- The application uses weighted random selection so topics with lower confidence appear more often.
