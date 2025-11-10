"""
PostgreSQL Synchronous Adapter
Drop-in replacement for sqlite3 connections
Uses psycopg2 for synchronous PostgreSQL access
"""

import psycopg2
import psycopg2.extras
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# PostgreSQL configuration
POSTGRES_CONFIG = {
    "host": "127.0.0.1",  # Use IPv4 explicitly
    "port": 5433,  # Docker PostgreSQL on port 5433
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}


def get_connection():
    """Get a PostgreSQL connection (synchronous)"""
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    # Use RealDictCursor to get results as dictionaries (similar to sqlite3.Row)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def convert_query_sqlite_to_pg(query: str) -> str:
    """
    Convert SQLite query syntax to PostgreSQL
    - Replace ? placeholders with %s
    - Replace AUTOINCREMENT with SERIAL
    - Other common conversions
    """
    # Replace SQLite placeholders with PostgreSQL placeholders
    # Note: This is a simple replacement, might need refinement
    return query.replace('?', '%s')


class PostgreSQLConnection:
    """
    Wrapper around psycopg2 connection to make it more sqlite3-like
    """

    def __init__(self, connection):
        self._connection = connection
        self._cursor = None

    def cursor(self):
        """Get a cursor"""
        self._cursor = self._connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return PostgreSQLCursor(self._cursor, self._connection)

    def commit(self):
        """Commit the transaction"""
        self._connection.commit()

    def rollback(self):
        """Rollback the transaction"""
        self._connection.rollback()

    def close(self):
        """Close the connection"""
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


class PostgreSQLCursor:
    """
    Wrapper around psycopg2 cursor to convert queries on the fly
    """

    def __init__(self, cursor, connection):
        self._cursor = cursor
        self._connection = connection

    def execute(self, query: str, params=None):
        """Execute a query, converting SQLite syntax to PostgreSQL"""
        # Convert ? to %s
        pg_query = convert_query_sqlite_to_pg(query)

        if params:
            self._cursor.execute(pg_query, params)
        else:
            self._cursor.execute(pg_query)

        return self

    def executemany(self, query: str, params_list):
        """Execute many queries"""
        pg_query = convert_query_sqlite_to_pg(query)
        self._cursor.executemany(pg_query, params_list)
        return self

    def fetchone(self):
        """Fetch one row"""
        return self._cursor.fetchone()

    def fetchall(self):
        """Fetch all rows"""
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        """Fetch many rows"""
        if size:
            return self._cursor.fetchmany(size)
        return self._cursor.fetchmany()

    @property
    def rowcount(self):
        """Get row count"""
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        """
        Get last inserted row ID
        Note: PostgreSQL doesn't have lastrowid like SQLite
        Use RETURNING id instead
        """
        # For PostgreSQL, we need to use RETURNING clause
        # This is a compatibility layer
        return None

    def close(self):
        """Close cursor"""
        self._cursor.close()


def connect(database=None):
    """
    SQLite3-compatible connect function that returns a PostgreSQL connection
    Ignores the database parameter and uses configured PostgreSQL
    """
    raw_conn = psycopg2.connect(**POSTGRES_CONFIG)
    return PostgreSQLConnection(raw_conn)
