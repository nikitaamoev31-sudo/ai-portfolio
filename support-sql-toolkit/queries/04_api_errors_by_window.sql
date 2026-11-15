-- Тикеты: «Записи с сайта не создаются, ошибка 500», «Виджет выдаёт ошибку»
-- Ошибки 5xx по эндпоинтам в 30-минутных окнах за последние сутки.
-- Если в одном окне много клиентов с 500 — это инцидент на нашей стороне, а не у клиента.
SELECT endpoint,
       date_trunc('hour', created_at)
         + INTERVAL '30 minutes' * (EXTRACT(MINUTE FROM created_at)::int / 30) AS window_start,
       COUNT(*)                              AS errors_5xx,
       COUNT(DISTINCT customer_id)           AS affected_customers,
       ROUND(AVG(latency_ms))::int           AS avg_latency_ms
FROM helpdesk.api_requests
WHERE status_code >= 500
  AND created_at >= helpdesk.report_now() - INTERVAL '24 hours'
GROUP BY endpoint, window_start
HAVING COUNT(*) >= 10
ORDER BY errors_5xx DESC;
