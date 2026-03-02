"""utils/db.py — Cadence Database Access Module

Provides shared database access for all pages in this application.
Import only these three names: get_connection, query_df, run_mutation.

  get_connection()
      Opens and returns a raw psycopg2 connection.
      Called internally by query_df and run_mutation.
      Raises ValueError with a clear message if any required env var is missing.

  query_df(sql, params=())
      Use for any SELECT query that returns rows.
      Cached for 300 seconds (5 minutes) via @st.cache_data to reduce
      round-trips to Supabase. Returns a pandas DataFrame.
      Returns an empty DataFrame (not an error) when the query produces no rows.

  run_mutation(sql, params=())
      Use for any INSERT, UPDATE, or DELETE operation.
      NOT cached. Commits the transaction, then clears the query_df cache
      automatically so the next read reflects the write.

Cache-clear rule:
  run_mutation() calls query_df.clear() automatically after every commit.
  In the calling page, always follow run_mutation() with st.rerun() so that
  cached reads re-execute and the UI reflects the new state immediately.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import streamlit as st
from dotenv import load_dotenv


def get_connection():
    """Open and return a psycopg2 connection to Supabase.

    Reads credentials from environment (loaded from .env via load_dotenv).
    Raises ValueError with a descriptive message if any required variable
    is absent so misconfiguration is immediately obvious.
    """
    load_dotenv()

    required = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Add them to your .env file (see .env.example)."
        )

    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 6543)),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode="require",
        connect_timeout=15,
    )


@st.cache_data(ttl=300, show_spinner=False)
def query_df(sql, params=()):
    """Execute a SELECT query and return results as a pandas DataFrame.

    Cached for 300 seconds. Returns an empty DataFrame when no rows match
    rather than raising an error — callers must handle the empty case.

    Args:
        sql:    SQL string with %s placeholders.
        params: Tuple of parameter values (default: empty tuple).

    Returns:
        pd.DataFrame of query results, possibly empty.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)
    finally:
        conn.close()


def run_mutation(sql, params=()):
    """Execute an INSERT, UPDATE, or DELETE, commit, and clear the read cache.

    NOT cached. After committing, calls query_df.clear() so the next call to
    query_df() fetches fresh data from the database.

    In the calling page, follow this function with st.rerun() to force
    Streamlit to re-render with the updated data.

    Args:
        sql:    SQL string with %s placeholders.
        params: Tuple of parameter values (default: empty tuple).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
        query_df.clear()
    finally:
        conn.close()
