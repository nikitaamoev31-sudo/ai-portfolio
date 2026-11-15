-- Отчёт для руководителя поддержки: нарушения SLA по первому ответу.
-- Учитываем и открытые тикеты без ответа: для них время считаем до текущего момента.
SELECT t.id AS ticket_id,
       t.subject,
       t.priority,
       t.status,
       sp.first_response_mins AS sla_mins,
       ROUND(EXTRACT(EPOCH FROM COALESCE(t.first_response_at, helpdesk.report_now()) - t.created_at) / 60)::int
                                AS response_mins,
       a.full_name              AS agent
FROM helpdesk.tickets t
JOIN helpdesk.sla_policies sp ON sp.priority = t.priority
LEFT JOIN helpdesk.agents a   ON a.id = t.agent_id
WHERE COALESCE(t.first_response_at, helpdesk.report_now()) - t.created_at
      > sp.first_response_mins * INTERVAL '1 minute'
ORDER BY (t.status <> 'resolved') DESC, t.priority = 'urgent' DESC, response_mins DESC;
