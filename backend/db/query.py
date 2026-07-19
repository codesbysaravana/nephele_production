"""
Shared read-only SQL execution with safety guards.
Used by both the main voice agent and the dashboard brain.
"""

from db import get_pool


def execute_safe_query(sql: str) -> str:
    """Execute a read-only SQL query against the DWH. Returns stringified results."""
    normalized = sql.strip().upper()
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]
    for keyword in forbidden:
        if normalized.startswith(keyword):
            return "Error: Only SELECT queries are allowed."

    try:
        pool = get_pool()
    except RuntimeError as e:
        return f"Error: {e}"

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(sql)
                rows = cur.fetchall()
                if not rows:
                    return "The query returned no results."
                col_names = [desc[0] for desc in cur.description]
                result_str = " | ".join(col_names) + "\n"
                for row in rows[:25]:
                    result_str += " | ".join(str(v) for v in row) + "\n"
                if len(rows) > 25:
                    result_str += f"... ({len(rows)} total rows, showing first 25)"
                return result_str
    except Exception as e:
        return f"SQL Error: {e}"
