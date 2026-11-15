-- Тикет: «Не могу войти в аккаунт»
-- Блокировки за последние сутки: сколько неудачных попыток было до блокировки и с каких IP.
-- Несколько попыток подряд с чужого IP — признак подбора пароля: эскалировать в безопасность.
WITH recent AS (
    SELECT * FROM helpdesk.login_events
    WHERE created_at >= helpdesk.report_now() - INTERVAL '24 hours'
)
SELECT r.customer_id,
       c.company,
       COUNT(*) FILTER (WHERE r.reason = 'wrong_password') AS wrong_password_attempts,
       COUNT(*) FILTER (WHERE r.reason = 'locked')         AS attempts_while_locked,
       COUNT(DISTINCT r.ip)                                AS distinct_ips,
       MIN(r.created_at)                                   AS first_failed_at,
       MAX(r.created_at)                                   AS last_failed_at
FROM recent r
JOIN helpdesk.customers c ON c.id = r.customer_id
WHERE NOT r.success
GROUP BY r.customer_id, c.company
HAVING COUNT(*) FILTER (WHERE r.reason = 'locked') > 0
ORDER BY wrong_password_attempts DESC;
