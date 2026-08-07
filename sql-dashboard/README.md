# SQL + Program Performance Dashboard

## Project Overview

This Week 3 internship project demonstrates relational SQL querying and an interactive Streamlit dashboard for program-performance analysis. Three realistic mock CSV source datasets are validated, loaded into SQLite, analyzed with SQL, and presented for a program manager.

## Features

- Three related CSV datasets: applicants, interns, and hackathon scores
- SQLite database with primary keys, foreign keys, and constraints
- SQL `JOIN` and `LEFT JOIN` analysis
- Domain-level aggregations and conversion analysis
- Interactive domain filtering across the complete dashboard
- Applicant-to-hackathon program funnel
- Completion/conversion rate by domain
- Average hackathon scores by domain
- Top-10 hackathon leaderboard
- Completion versus dropout analysis

## Data Model

```text
applicants
    applicant_id (PRIMARY KEY)
          |
          | applicant_id
          v
interns
    intern_id (PRIMARY KEY)
    applicant_id (FOREIGN KEY)
          |
          | intern_id
          v
hackathon_scores
    intern_id (PRIMARY KEY + FOREIGN KEY)
```

`applicants.applicant_id` connects an application to its internship record. `interns.intern_id` connects an intern to a hackathon score. Intern and score domains are kept consistent with their related records.

## Project Structure

```text
week3-sql-dashboard/
├── data/
│   ├── applicants.csv
│   ├── interns.csv
│   └── hackathon_scores.csv
├── database/
│   └── nextgen.db
├── scripts/
│   └── create_database.py
├── Week3_SQL_Queries.ipynb
├── dashboard.py
├── requirements.txt
├── README.md
├── .gitignore
└── screenshots/
    └── README.md
```

## Installation

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Create SQLite Database

```bash
python scripts/create_database.py
```

The three CSV files in `data/` are the source datasets. This script validates their columns and relationships, then rebuilds the SQLite database idempotently at `database/nextgen.db` with foreign-key enforcement enabled.

## Run SQL Notebook

```bash
jupyter notebook Week3_SQL_Queries.ipynb
```

The notebook first previews all three tables, then runs the required analytical queries.

## Run Dashboard

```bash
streamlit run dashboard.py
```

If the database is missing or incomplete, the app displays a setup message rather than an obscure traceback.

## Dashboard Components

The sidebar domain filter is loaded dynamically from SQLite and updates all relevant content:

1. KPI cards for applicants, interns, completed interns, conversion rate, and average score.
2. A funnel showing applicants through hackathon participants.
3. Conversion rate by domain using applicant-preserving `LEFT JOIN` logic.
4. Average hackathon score by domain.
5. A filtered top-10 leaderboard with rank, intern, name, university, domain, and score.
6. A supporting completion-versus-dropout chart.

All user-selected domains are passed as SQL parameters rather than concatenated into SQL strings.

## SQL Queries

- **Query 1:** Completed interns per domain.
- **Query 2:** Average hackathon score per domain.
- **Query 3:** Interns scoring 85 or above using joins.
- **Query 4:** Applied-to-completed conversion per domain using `LEFT JOIN`, decimal arithmetic, and distinct counts.
- **Query 5:** Universities producing the highest-scoring hackathon interns on average.
- **Bonus:** Completion versus dropout by domain using conditional aggregation.

## Screenshots / Demo

See `screenshots/README.md` for the recommended All Domains, filtered-domain, and leaderboard screenshots.

## Technologies

- Python
- pandas
- SQLite
- SQL
- Streamlit
- Plotly
- Jupyter Notebook

## Validation

The database-loading script validates source columns, uniqueness, foreign-key references, domain consistency, permitted statuses, and score boundaries. The generated database can be checked with:

```bash
python -c "import sqlite3; c=sqlite3.connect('database/nextgen.db'); print(c.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\").fetchall()); print(c.execute('PRAGMA foreign_key_check').fetchall())"
```
