from django.db.backends.base.base import BaseDatabaseWrapper


def quote_id(conn: BaseDatabaseWrapper, sql: str, *names: str) -> str:
    """Format SQL with properly quoted identifiers.

    Uses the connection's backend to quote identifier names, so it works
    with both MySQL (backticks) and Postgres (double quotes).

    Usage::

        cursor.execute(quote_id(conn, "DROP DATABASE IF EXISTS %s", db_name))
    """
    return sql % tuple(conn.ops.quote_name(n) for n in names)
