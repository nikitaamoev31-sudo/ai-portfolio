-- ABC analysis: products that make 80% (A), next 15% (B) and last 5% (C) of net revenue
WITH rev AS (
    SELECT p.product_id, p.name, p.category,
           SUM(i.unit_price * i.qty * (1 - i.returned)) AS revenue
    FROM order_items i JOIN products p ON p.product_id = i.product_id
    GROUP BY p.product_id
),
ranked AS (
    SELECT *, SUM(revenue) OVER (ORDER BY revenue DESC ROWS UNBOUNDED PRECEDING)
              / SUM(revenue) OVER () AS cum_share
    FROM rev
)
SELECT product_id, name, category, ROUND(revenue, 2) AS revenue,
       ROUND(100 * cum_share, 1) AS cum_share_pct,
       CASE WHEN cum_share <= 0.80 THEN 'A' WHEN cum_share <= 0.95 THEN 'B' ELSE 'C' END AS abc_class
FROM ranked
ORDER BY revenue DESC;
