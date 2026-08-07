"""Streamlit dashboard for performance project."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except ImportError:  # pragma: no cover - allows a useful setup message in minimal environments.
    px = None

ROOT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = ROOT_DIR / "database" / "nextgen.db"

st.set_page_config(
    page_title="Program Performance Dashboard",
    page_icon="📊",
    layout="wide",
)


def get_connection() -> sqlite3.Connection:
    """Open a read-only SQLite connection with foreign-key checks enabled."""
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH}. Run `python scripts/create_database.py` "
            "first to load the CSV files into SQLite."
        )
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    required_tables = {"applicants", "interns", "hackathon_scores"}
    tables = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    missing = required_tables - tables
    if missing:
        connection.close()
        raise RuntimeError(f"Database is missing required tables: {sorted(missing)}")
    return connection


def query_dataframe(query: str, params: tuple = ()) -> pd.DataFrame:
    """Run a parameterized query against a short-lived connection."""
    connection = get_connection()
    try:
        return pd.read_sql_query(query, connection, params=params)
    finally:
        connection.close()


def domain_clause(domain: str, column: str = "a.domain") -> tuple[str, tuple]:
    """Return a safe optional SQL predicate and its parameter."""
    if domain == "All Domains":
        return "", ()
    return f" AND {column} = ?", (domain,)


@st.cache_data
def load_domains() -> list[str]:
    """Load domain choices from the database."""
    result = query_dataframe("SELECT DISTINCT domain FROM applicants ORDER BY domain")
    return result["domain"].tolist()


@st.cache_data
def get_kpis(domain: str) -> dict[str, float]:
    """Calculate the filtered KPI values with SQL."""
    condition, params = domain_clause(domain)
    query = f"""
        SELECT
            (SELECT COUNT(*) FROM applicants WHERE 1=1 {condition.replace('a.domain', 'domain')}) AS total_applicants,
            (SELECT COUNT(*) FROM interns i JOIN applicants a ON a.applicant_id = i.applicant_id
             WHERE 1=1 {condition}) AS total_interns,
            (SELECT COUNT(*) FROM interns i JOIN applicants a ON a.applicant_id = i.applicant_id
             WHERE i.completion_status = 'Completed' {condition}) AS completed_interns,
            (SELECT ROUND(AVG(h.score), 2) FROM hackathon_scores h
             JOIN interns i ON i.intern_id = h.intern_id
             WHERE 1=1 {condition.replace('a.domain', 'i.domain')}) AS average_score,
            (SELECT COUNT(*) FROM hackathon_scores h JOIN interns i ON i.intern_id = h.intern_id
             WHERE 1=1 {condition.replace('a.domain', 'i.domain')}) AS hackathon_participants
    """
    # The same domain parameter is used once for each subquery that needs it.
    parameter_count = query.count("?")
    values = params * parameter_count
    row = query_dataframe(query, values).iloc[0]
    total_applicants = int(row["total_applicants"] or 0)
    completed = int(row["completed_interns"] or 0)
    return {
        "total_applicants": total_applicants,
        "total_interns": int(row["total_interns"] or 0),
        "completed_interns": completed,
        "conversion_rate": round(100 * completed / total_applicants, 2) if total_applicants else 0,
        "average_score": float(row["average_score"] or 0),
        "hackathon_participants": int(row["hackathon_participants"] or 0),
    }


@st.cache_data
def get_conversion_data(domain: str) -> pd.DataFrame:
    """Return the LEFT JOIN conversion analysis for the selected domain."""
    condition, params = domain_clause(domain)
    query = f"""
        SELECT a.domain,
               COUNT(DISTINCT a.applicant_id) AS total_applicants,
               COUNT(DISTINCT i.intern_id) AS total_completed,
               ROUND(100.0 * COUNT(DISTINCT i.intern_id)
                     / NULLIF(COUNT(DISTINCT a.applicant_id), 0), 2) AS conversion_rate_pct
        FROM applicants a
        LEFT JOIN interns i
          ON a.applicant_id = i.applicant_id
         AND i.completion_status = 'Completed'
        WHERE 1=1 {condition}
        GROUP BY a.domain
        ORDER BY conversion_rate_pct DESC
    """
    return query_dataframe(query, params)


@st.cache_data
def get_average_scores(domain: str) -> pd.DataFrame:
    """Return average scored performance by domain."""
    condition, params = domain_clause(domain, "i.domain")
    query = f"""
        SELECT i.domain, ROUND(AVG(h.score), 2) AS average_score
        FROM interns i
        JOIN hackathon_scores h ON i.intern_id = h.intern_id
        WHERE 1=1 {condition}
        GROUP BY i.domain
        ORDER BY average_score DESC
    """
    return query_dataframe(query, params)


@st.cache_data
def get_leaderboard(domain: str) -> pd.DataFrame:
    """Return the filtered top ten hackathon scores."""
    condition, params = domain_clause(domain, "i.domain")
    query = f"""
        SELECT i.intern_id AS "Intern ID", a.name AS "Name", a.university AS "University",
               i.domain AS "Domain", ROUND(h.score, 2) AS "Score"
        FROM interns i
        JOIN applicants a ON a.applicant_id = i.applicant_id
        JOIN hackathon_scores h ON h.intern_id = i.intern_id
        WHERE 1=1 {condition}
        ORDER BY h.score DESC, a.name
        LIMIT 10
    """
    result = query_dataframe(query, params)
    if not result.empty:
        result.insert(0, "Rank", range(1, len(result) + 1))
    return result


@st.cache_data
def get_completion_breakdown(domain: str) -> pd.DataFrame:
    """Return completed and dropout counts for the optional chart."""
    condition, params = domain_clause(domain, "domain")
    query = f"""
        SELECT domain,
               SUM(CASE WHEN completion_status = 'Completed' THEN 1 ELSE 0 END) AS completed,
               SUM(CASE WHEN completion_status = 'Dropped Out' THEN 1 ELSE 0 END) AS dropped_out
        FROM interns
        WHERE 1=1 {condition}
        GROUP BY domain
        ORDER BY completed DESC
    """
    return query_dataframe(query, params)


def render_dashboard() -> None:
    """Render the complete dashboard page."""
    st.title("Program Performance Dashboard")
    st.caption("Interactive analysis of applications, internship completion, and hackathon performance.")

    try:
        domains = load_domains()
        selected_domain = st.sidebar.selectbox("Domain", ["All Domains", *domains])
        st.sidebar.markdown("---")
        st.sidebar.caption("Data source: database/nextgen.db")
        kpis = get_kpis(selected_domain)
        conversion = get_conversion_data(selected_domain)
        averages = get_average_scores(selected_domain)
        leaderboard = get_leaderboard(selected_domain)
        breakdown = get_completion_breakdown(selected_domain)
    except (FileNotFoundError, RuntimeError, sqlite3.Error, ValueError) as error:
        st.error(str(error))
        st.info("Build the data and database, then refresh this page.")
        return

    st.markdown(f"**Current view:** {selected_domain}")
    cards = st.columns(5)
    cards[0].metric("Total Applicants", f"{kpis['total_applicants']:,}")
    cards[1].metric("Selected / Interns", f"{kpis['total_interns']:,}")
    cards[2].metric("Completed Interns", f"{kpis['completed_interns']:,}")
    cards[3].metric("Completion Rate", f"{kpis['conversion_rate']:.2f}%")
    cards[4].metric("Average Hackathon Score", f"{kpis['average_score']:.2f}" if kpis["average_score"] else "—")

    st.markdown("### Program Funnel")
    funnel = pd.DataFrame(
        {
            "Stage": ["Applicants", "Selected / Interns", "Completed Interns", "Hackathon Participants"],
            "Count": [
                kpis["total_applicants"],
                kpis["total_interns"],
                kpis["completed_interns"],
                kpis["hackathon_participants"],
            ],
        }
    )
    if px:
        figure = px.funnel(funnel, y="Stage", x="Count", title="Participant movement through the program")
        figure.update_layout(height=360, margin=dict(l=20, r=20, t=60, b=20))
        st.plotly_chart(figure, use_container_width=True)
    else:
        st.dataframe(funnel, use_container_width=True, hide_index=True)

    left, right = st.columns(2)
    with left:
        st.markdown("### Conversion Rate by Domain")
        if conversion.empty:
            st.info("No conversion data is available for this selection.")
        elif px:
            figure = px.bar(
                conversion,
                x="domain",
                y="conversion_rate_pct",
                text="conversion_rate_pct",
                labels={"domain": "Domain", "conversion_rate_pct": "Conversion Rate (%)"},
                title="Applied to completed internship rate",
            )
            figure.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
            figure.update_layout(yaxis_range=[0, 100], height=390, margin=dict(t=60, b=20))
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.dataframe(conversion, use_container_width=True, hide_index=True)

    with right:
        st.markdown("### Average Hackathon Score by Domain")
        if averages.empty:
            st.info("No hackathon scores are available for this selection.")
        elif px:
            figure = px.bar(
                averages,
                x="domain",
                y="average_score",
                text="average_score",
                labels={"domain": "Domain", "average_score": "Average Score"},
                title="Average score out of 100",
            )
            figure.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            figure.update_layout(yaxis_range=[0, 100], height=390, margin=dict(t=60, b=20))
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.dataframe(averages, use_container_width=True, hide_index=True)

    st.markdown("### Top 10 Hackathon Leaderboard")
    if leaderboard.empty:
        st.info("No hackathon scores are available for this selection.")
    else:
        st.dataframe(
            leaderboard,
            use_container_width=True,
            hide_index=True,
            column_config={"Score": st.column_config.NumberColumn("Score", format="%.2f")},
        )

    st.markdown("### Completion vs Dropout")
    if not breakdown.empty and px:
        chart_data = breakdown.melt("domain", var_name="Outcome", value_name="Interns")
        figure = px.bar(
            chart_data,
            x="domain",
            y="Interns",
            color="Outcome",
            barmode="group",
            labels={"domain": "Domain", "Interns": "Number of interns"},
            title="Program outcomes by domain",
        )
        figure.update_layout(height=360, margin=dict(t=60, b=20))
        st.plotly_chart(figure, use_container_width=True)
    elif breakdown.empty:
        st.info("No internship outcome data is available for this selection.")

    st.caption("Program Performance")


if __name__ == "__main__":
    render_dashboard()
