-- Monthly net revenue (returns excluded), orders, AOV and month-over-month growth
WITH monthly AS (
    SELECT substr(o.order_date, 1, 7)                          AS month,
           COUNT(DISTINCT o.order_id)                          AS orders,
           ROUND(SUM(i.unit_price * i.qty * (1 - i.returned)), 2) AS net_revenue
    FROM orders o
    JOIN order_items i ON i.order_id = o.order_id
    GROUP BY 1
)
SELECT month,
       orders,
       net_revenue,
       ROUND(net_revenue / orders, 2)                                         AS aov,
       ROUND(100.0 * (net_revenue - LAG(net_revenue) OVER (ORDER BY month))
             / LAG(net_revenue) OVER (ORDER BY month), 1)                     AS mom_growth_pct
FROM monthly
ORDER BY month;
