# Job Tracker API

REST API на **Java 17 + Spring Boot 3** для учёта откликов на вакансии: компании, должности, статусы воронки (найдено → отклик → тестовое → интервью → оффер / отказ) и статистика конверсии.

## Стек
Java 17 · Spring Boot 3 (Web, Data JPA, Validation) · PostgreSQL / H2 · Hibernate · REST · OpenAPI (Swagger UI) · JUnit 5 · Mockito · MockMvc · Docker, Docker Compose

## Возможности
- CRUD откликов: `GET/POST/PUT/DELETE /api/applications`
- Пагинация и сортировка, фильтр по статусу и поиск по компании
- Смена статуса: `PATCH /api/applications/{id}/status` (при переходе в `APPLIED` дата отклика ставится автоматически)
- Статистика воронки: `GET /api/applications/stats` — количество по статусам и % ответов работодателей
- Валидация входных данных и единый формат ошибок (RFC 7807 `ProblemDetail`)
- Документация API: Swagger UI
- Unit-тесты сервиса (Mockito) и интеграционные тесты API (MockMvc + H2)

## Архитектура
```
controller  →  service  →  repository  →  БД
   ↑ DTO (record)    ↑ бизнес-логика   ↑ Spring Data JPA
exception/GlobalExceptionHandler — обработка ошибок
```

## Запуск
**Быстро (встроенная БД H2, ничего ставить не нужно):**
```bash
mvn spring-boot:run
```
Swagger UI: http://localhost:8080/swagger-ui.html

**С PostgreSQL в Docker:**
```bash
docker compose up --build
```

**Тесты:**
```bash
mvn test
```

## Пример
```bash
curl -X POST localhost:8080/api/applications \
  -H "Content-Type: application/json" \
  -d '{"company":"Acme","position":"AI Automation Engineer","salaryUsd":1000}'

curl -X PATCH localhost:8080/api/applications/1/status \
  -H "Content-Type: application/json" -d '{"status":"APPLIED"}'

curl localhost:8080/api/applications/stats
```

---
Разработано с использованием AI-ассистента (Claude Code).
