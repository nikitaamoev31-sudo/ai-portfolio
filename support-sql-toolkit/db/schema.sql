-- Учебная база SaaS-сервиса онлайн-записи (клиенты, тарифы, оплаты, тикеты, логи API).
-- Структура похожа на ту, с которой работает поддержка L1/L2 в продуктовых компаниях.

SET client_min_messages = warning;
DROP SCHEMA IF EXISTS helpdesk CASCADE;
CREATE SCHEMA helpdesk;
SET search_path TO helpdesk;

CREATE TABLE plans (
    id            SERIAL PRIMARY KEY,
    code          TEXT UNIQUE NOT NULL,          -- start / pro / business
    name          TEXT NOT NULL,
    price_monthly NUMERIC(10,2) NOT NULL,
    max_staff     INT NOT NULL                   -- лимит сотрудников на тарифе
);

CREATE TABLE customers (
    id          SERIAL PRIMARY KEY,
    company     TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    country     TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL
);

CREATE TABLE subscriptions (
    id           SERIAL PRIMARY KEY,
    customer_id  INT NOT NULL REFERENCES customers(id),
    plan_id      INT NOT NULL REFERENCES plans(id),
    status       TEXT NOT NULL CHECK (status IN ('trial','active','past_due','cancelled')),
    started_at   TIMESTAMP NOT NULL,
    paid_until   DATE
);

CREATE TABLE payments (
    id              SERIAL PRIMARY KEY,
    customer_id     INT NOT NULL REFERENCES customers(id),
    amount          NUMERIC(10,2) NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('succeeded','failed','refunded')),
    provider_txn_id TEXT NOT NULL,               -- id операции у платёжного провайдера
    created_at      TIMESTAMP NOT NULL
);

CREATE TABLE staff (                             -- сотрудники клиента, которых он завёл в сервис
    id           SERIAL PRIMARY KEY,
    customer_id  INT NOT NULL REFERENCES customers(id),
    full_name    TEXT NOT NULL,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE agents (                            -- сотрудники поддержки
    id         SERIAL PRIMARY KEY,
    full_name  TEXT NOT NULL,
    line       TEXT NOT NULL CHECK (line IN ('L1','L2'))
);

CREATE TABLE sla_policies (
    priority             TEXT PRIMARY KEY CHECK (priority IN ('low','normal','high','urgent')),
    first_response_mins  INT NOT NULL,
    resolution_hours     INT NOT NULL
);

CREATE TABLE tickets (
    id                 SERIAL PRIMARY KEY,
    customer_id        INT NOT NULL REFERENCES customers(id),
    agent_id           INT REFERENCES agents(id),
    subject            TEXT NOT NULL,
    category           TEXT NOT NULL,         -- billing / login / integration / booking / other
    priority           TEXT NOT NULL REFERENCES sla_policies(priority),
    status             TEXT NOT NULL CHECK (status IN ('open','pending','escalated','resolved')),
    created_at         TIMESTAMP NOT NULL,
    first_response_at  TIMESTAMP,
    resolved_at        TIMESTAMP,
    csat               INT CHECK (csat BETWEEN 1 AND 5)
);

CREATE TABLE login_events (
    id           SERIAL PRIMARY KEY,
    customer_id  INT NOT NULL REFERENCES customers(id),
    success      BOOLEAN NOT NULL,
    reason       TEXT,                         -- wrong_password / locked / sso_error
    ip           TEXT NOT NULL,
    created_at   TIMESTAMP NOT NULL
);

CREATE TABLE api_requests (                      -- лог запросов клиентов к публичному API
    id           SERIAL PRIMARY KEY,
    customer_id  INT NOT NULL REFERENCES customers(id),
    endpoint     TEXT NOT NULL,
    status_code  INT NOT NULL,
    latency_ms   INT NOT NULL,
    created_at   TIMESTAMP NOT NULL
);

CREATE INDEX ON payments (customer_id, created_at);
CREATE INDEX ON tickets (status, priority);
CREATE INDEX ON api_requests (created_at, status_code);
CREATE INDEX ON login_events (customer_id, created_at);
