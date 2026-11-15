-- Очередь на смену: открытые тикеты по приоритету, сколько минут осталось до нарушения SLA
-- (отрицательное значение — SLA уже нарушен), без назначенного сотрудника — первыми.
SELECT t.id AS ticket_id,
       c.company,
       t.subject,
       t.priority,
       t.status,
       COALESCE(a.full_name, '— не назначен —') AS agent,
       CASE WHEN t.first_response_at IS NULL THEN
            ROUND(sp.first_response_mins
                  - EXTRACT(EPOCH FROM helpdesk.report_now() - t.created_at) / 60)::int
       END AS mins_to_first_response_sla
FROM helpdesk.tickets t
JOIN helpdesk.customers c     ON c.id = t.customer_id
JOIN helpdesk.sla_policies sp ON sp.priority = t.priority
LEFT JOIN helpdesk.agents a   ON a.id = t.agent_id
WHERE t.status <> 'resolved'
ORDER BY (t.agent_id IS NULL) DESC,
         CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END,
         t.created_at;
