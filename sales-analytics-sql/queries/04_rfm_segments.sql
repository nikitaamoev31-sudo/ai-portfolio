-- RFM segmentation: recency, frequency, monetary scored 1-5 with NTILE
WITH stats AS (
    SELECT o.customer_id,
           julianday('2026-12-01') - julianday(MAX(o.order_date))   AS recency_days,
           COUNT(DISTINCT o.order_id)                                AS frequency,
           SUM(i.unit_price * i.qty * (1 - i.returned))              AS monetary
    FROM orders o JOIN order_items i ON i.order_id = o.order_id
    GROUP BY o.customer_id
),
scored AS (
    SELECT *,
           NTILE(5) OVER (ORDER BY recency_days DESC) AS r,
           NTILE(5) OVER (ORDER BY frequency)         AS f,
           NTILE(5) OVER (ORDER BY monetary)          AS m
    FROM stats
)
SELECT CASE
         WHEN r >= 4 AND f >= 4 THEN 'Champions'
         WHEN r >= 3 AND f >= 3 THEN 'Loyal'
         WHEN r >= 4                THEN 'New / promising'
         WHEN r <= 2 AND f >= 3     THEN 'At risk'
         ELSE 'Hibernating'
       END                          AS segment,
       COUNT(*)                     AS customers,
       ROUND(AVG(monetary), 2)      AS avg_revenue,
       ROUND(SUM(monetary), 2)      AS total_revenue
FROM scored
GROUP BY segment
ORDER BY total_revenue DESC;
