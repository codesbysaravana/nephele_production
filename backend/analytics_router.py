"""
Analytics REST API — Serves chart-ready JSON from the Star Schema.
"""

from fastapi import APIRouter, HTTPException
from db import get_pool

router = APIRouter(tags=["Analytics"])


def _query(sql: str) -> list[tuple]:
    try:
        pool = get_pool()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()


def _chart(sql: str) -> dict:
    rows = _query(sql)
    return {"labels": [r[0] for r in rows], "values": [r[1] for r in rows]}


@router.get("/api/analytics/revenue-by-day")
async def revenue_by_day():
    return _chart("""
        SELECT sale_date::TEXT, SUM(amount)::FLOAT
        FROM fact_sales GROUP BY sale_date ORDER BY sale_date
    """)


@router.get("/api/analytics/top-customers")
async def top_customers():
    return _chart("""
        SELECT customer_name, total_spent::FLOAT
        FROM dim_users ORDER BY spending_rank LIMIT 10
    """)


@router.get("/api/analytics/spending-distribution")
async def spending_distribution():
    return _chart("""
        SELECT
            CASE
                WHEN total_spent < 50 THEN 'Low (<$50)'
                WHEN total_spent < 150 THEN 'Medium ($50-$150)'
                WHEN total_spent < 300 THEN 'High ($150-$300)'
                ELSE 'VIP ($300+)'
            END AS tier,
            COUNT(*)::INT
        FROM dim_users GROUP BY tier ORDER BY MIN(total_spent)
    """)


@router.get("/api/analytics/running-revenue")
async def running_revenue():
    return _chart("""
        SELECT sale_date::TEXT, MAX(running_daily_revenue)::FLOAT
        FROM fact_sales GROUP BY sale_date ORDER BY sale_date
    """)


@router.get("/api/analytics/revenue-growth")
async def revenue_growth():
    return _chart("""
        SELECT sale_date, growth_pct FROM (
            SELECT sale_date::TEXT,
                ROUND((daily_rev - LAG(daily_rev) OVER (ORDER BY sale_date))
                    / NULLIF(LAG(daily_rev) OVER (ORDER BY sale_date), 0) * 100, 1
                )::FLOAT AS growth_pct
            FROM (SELECT sale_date, SUM(amount) AS daily_rev FROM fact_sales GROUP BY sale_date) d
        ) g WHERE growth_pct IS NOT NULL
    """)
