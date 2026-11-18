-- Cohort retention: share of each signup cohort that ordered again N months later
-- (NULL = that month has not happened yet for the cohort)
WITH cohort AS (
    SELECT customer_id, substr(signup_date, 1, 7) AS cohort,
           CAST(substr(signup_date, 1, 4) AS INT) * 12 + CAST(substr(signup_date, 6, 2) AS INT) AS cohort_idx
    FROM customers
),
activity AS (
    SELECT DISTINCT c.cohort, o.customer_id,
           CAST(substr(o.order_date, 1, 4) AS INT) * 12 + CAST(substr(o.order_date, 6, 2) AS INT)
           - c.cohort_idx AS month_n
    FROM orders o JOIN cohort c ON c.customer_id = o.customer_id
),
sizes AS (
    SELECT cohort, cohort_idx, COUNT(*) AS size FROM cohort GROUP BY cohort, cohort_idx
),
last AS (
    SELECT MAX(CAST(substr(order_date, 1, 4) AS INT) * 12 + CAST(substr(order_date, 6, 2) AS INT)) AS idx FROM orders
)
SELECT s.cohort,
       s.size,
       CASE WHEN s.cohort_idx + 1 <= l.idx THEN ROUND(100.0 * SUM(a.month_n = 1) / s.size, 1) END AS m1_pct,
       CASE WHEN s.cohort_idx + 2 <= l.idx THEN ROUND(100.0 * SUM(a.month_n = 2) / s.size, 1) END AS m2_pct,
       CASE WHEN s.cohort_idx + 3 <= l.idx THEN ROUND(100.0 * SUM(a.month_n = 3) / s.size, 1) END AS m3_pct
FROM sizes s
JOIN activity a ON a.cohort = s.cohort
CROSS JOIN last l
GROUP BY s.cohort, s.size, s.cohort_idx, l.idx
ORDER BY s.cohort;
