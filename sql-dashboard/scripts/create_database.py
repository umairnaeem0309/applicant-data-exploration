"""Build the SQLite database from the three source CSV files."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DATABASE_DIR = ROOT_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "nextgen.db"

REQUIRED_COLUMNS = {
    "applicants.csv": ["applicant_id", "name", "domain", "university", "application_date", "status"],
    "interns.csv": ["intern_id", "applicant_id", "domain", "start_date", "completion_status"],
    "hackathon_scores.csv": ["intern_id", "score", "domain"],
}


def read_csv(filename: str) -> list[dict[str, str]]:
    """Read a required CSV and validate its header."""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Required source file is missing: {path}")
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = set(REQUIRED_COLUMNS[filename]) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{filename} is missing required columns: {sorted(missing)}")
        return list(reader)


def validate_relationships(applicants: list[dict], interns: list[dict], scores: list[dict]) -> None:
    """Validate source relationships before inserting rows."""
    applicants_by_id = {row["applicant_id"]: row for row in applicants}
    interns_by_id = {row["intern_id"]: row for row in interns}
    if len(applicants_by_id) != len(applicants):
        raise ValueError("applicants.csv contains duplicate applicant_id values")
    if len(interns_by_id) != len(interns):
        raise ValueError("interns.csv contains duplicate intern_id values")
    if any(row["applicant_id"] not in applicants_by_id for row in interns):
        raise ValueError("interns.csv contains an unknown applicant_id")
    if any(applicants_by_id[row["applicant_id"]]["status"] != "Selected" for row in interns):
        raise ValueError("Only applicants with status 'Selected' can appear in interns.csv")
    if any(row["intern_id"] not in interns_by_id for row in scores):
        raise ValueError("hackathon_scores.csv contains an unknown intern_id")
    if any(row["domain"] != applicants_by_id[row["applicant_id"]]["domain"] for row in interns):
        raise ValueError("Intern domains do not match their applicants")
    if any(row["domain"] != interns_by_id[row["intern_id"]]["domain"] for row in scores):
        raise ValueError("Score domains do not match their interns")
    if any(row["status"] not in {"Selected", "Rejected", "Under Review"} for row in applicants):
        raise ValueError("Invalid applicant status found")
    if any(row["completion_status"] not in {"Completed", "Dropped Out"} for row in interns):
        raise ValueError("Invalid completion status found")
    if any(not 50 <= float(row["score"]) <= 100 for row in scores):
        raise ValueError("Hackathon scores must be between 50 and 100")


def create_database() -> Path:
    """Rebuild the SQLite database and return its path."""
    applicants = read_csv("applicants.csv")
    interns = read_csv("interns.csv")
    scores = read_csv("hackathon_scores.csv")
    validate_relationships(applicants, interns, scores)
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            DROP TABLE IF EXISTS hackathon_scores;
            DROP TABLE IF EXISTS interns;
            DROP TABLE IF EXISTS applicants;

            CREATE TABLE applicants (
                applicant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                university TEXT NOT NULL,
                application_date TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('Selected', 'Rejected', 'Under Review'))
            );

            CREATE TABLE interns (
                intern_id TEXT PRIMARY KEY,
                applicant_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                start_date TEXT NOT NULL,
                completion_status TEXT NOT NULL CHECK (completion_status IN ('Completed', 'Dropped Out')),
                FOREIGN KEY (applicant_id) REFERENCES applicants(applicant_id)
            );

            CREATE TABLE hackathon_scores (
                intern_id TEXT PRIMARY KEY,
                score REAL NOT NULL CHECK (score >= 50 AND score <= 100),
                domain TEXT NOT NULL,
                FOREIGN KEY (intern_id) REFERENCES interns(intern_id)
            );
            """
        )
        connection.executemany(
            "INSERT INTO applicants VALUES (:applicant_id, :name, :domain, :university, :application_date, :status)",
            applicants,
        )
        connection.executemany(
            "INSERT INTO interns VALUES (:intern_id, :applicant_id, :domain, :start_date, :completion_status)",
            interns,
        )
        connection.executemany(
            "INSERT INTO hackathon_scores VALUES (:intern_id, :score, :domain)",
            scores,
        )

    print(f"Database created: {DATABASE_PATH}")
    print(f"Tables loaded: applicants={len(applicants)}, interns={len(interns)}, hackathon_scores={len(scores)}")
    return DATABASE_PATH


if __name__ == "__main__":
    create_database()
