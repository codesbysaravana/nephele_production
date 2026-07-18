-- ======================================================
-- Create Final Tables
-- ======================================================

CREATE TABLE IF NOT EXISTS dim_users (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT,
    total_spent NUMERIC(12,2),
    spending_rank INTEGER
);

CREATE TABLE IF NOT EXISTS fact_sales (
    transaction_id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES dim_users(customer_id),
    amount NUMERIC(12,2),
    sale_date DATE,
    running_daily_revenue NUMERIC(12,2)
);

-- ======================================================
-- Populate Dimension Table
-- ======================================================

WITH extracted AS (
    SELECT
        raw_data->'customer'->>'id' AS customer_id,
        raw_data->'customer'->>'name' AS customer_name,
        raw_data->'transaction'->>'id' AS transaction_id,
        (raw_data->'transaction'->>'amount')::NUMERIC AS amount,
        (raw_data->'transaction'->>'date')::DATE AS sale_date
    FROM raw_transactions
),
customer_totals AS (
    SELECT
        customer_id,
        customer_name,
        SUM(amount) AS total_spent,
        RANK() OVER (ORDER BY SUM(amount) DESC) AS spending_rank
    FROM extracted
    GROUP BY customer_id, customer_name
)
INSERT INTO dim_users (
    customer_id, customer_name, total_spent, spending_rank
)
SELECT
    customer_id, customer_name, total_spent, spending_rank
FROM customer_totals
ON CONFLICT (customer_id) DO UPDATE SET total_spent = EXCLUDED.total_spent, spending_rank = EXCLUDED.spending_rank;


-- ======================================================
-- Populate Fact Table
-- ======================================================

WITH extracted AS (
    SELECT
        raw_data->'customer'->>'id' AS customer_id,
        raw_data->'transaction'->>'id' AS transaction_id,
        (raw_data->'transaction'->>'amount')::NUMERIC AS amount,
        (raw_data->'transaction'->>'date')::DATE AS sale_date
    FROM raw_transactions
),
sales_running_total AS (
    SELECT
        transaction_id,
        customer_id,
        amount,
        sale_date,
        SUM(amount) OVER (
            ORDER BY sale_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_daily_revenue
    FROM extracted
)
INSERT INTO fact_sales (
    transaction_id, customer_id, amount, sale_date, running_daily_revenue
)
SELECT
    transaction_id, customer_id, amount, sale_date, running_daily_revenue
FROM sales_running_total
ON CONFLICT (transaction_id) DO NOTHING;