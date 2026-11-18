-- Return rate and lost revenue by category
SELECT p.category,
       COUNT(*)                                               AS items_sold,
       SUM(i.returned)                                        AS items_returned,
       ROUND(100.0 * SUM(i.returned) / COUNT(*), 1)           AS return_rate_pct,
       ROUND(SUM(i.unit_price * i.qty * i.returned), 2)       AS lost_revenue
FROM order_items i JOIN products p ON p.product_id = i.product_id
GROUP BY p.category
ORDER BY return_rate_pct DESC;
