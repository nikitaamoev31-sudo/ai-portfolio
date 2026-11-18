# QA: API test suite for job-tracker-api

**Role:** QA Engineer (manual + API automation) · **Stack:** Python, pytest, requests, REST, GitHub Actions

Black-box testing of my own [job-tracker-api](../job-tracker-api) (Java / Spring Boot): test design, automated API checks and bug reports with root cause — the way I would test a service at work.

## What is inside
- [test-cases.md](test-cases.md) — 20 test cases: happy paths, validation, errors, pagination, statistics.
- [bug-reports.md](bug-reports.md) — **3 real defects** found by exploratory testing, with steps, expected/actual, severity and a fix idea.
- [tests/](tests) — pytest suite covering every test case: isolated data per test (unique company names) and cleanup after each test.

Known bugs are tests marked `xfail(strict=True)`: CI is green while the bug exists and goes red the moment someone fixes it — so the ticket is not forgotten.

## Run
```bash
# 1) start the API (needs Java 17)
cd ../job-tracker-api && mvn -q spring-boot:run &
# 2) run the tests
pip install -r requirements.txt && pytest -q
```
`BASE_URL` (default `http://localhost:8080`) points the suite at another environment.

In CI the API is built, started and tested on every push — see `.github/workflows/ci.yml`, job `qa-api-tests`.
