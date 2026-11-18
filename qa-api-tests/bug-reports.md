# Bug reports — job-tracker-api

Found during exploratory testing. Each bug has an automated check in [`tests/test_known_bugs.py`](tests/test_known_bugs.py).

---

### BUG-1 · Filters `status` and `company` cannot be combined
**Severity:** Major · **Priority:** High · **Endpoint:** `GET /api/applications`

**Steps**
1. `POST /api/applications` `{"company":"Acme","position":"QA","status":"OFFER"}`
2. `POST /api/applications` `{"company":"Other","position":"QA","status":"OFFER"}`
3. `GET /api/applications?status=OFFER&company=Acme`

**Expected:** only the Acme application.
**Actual:** both applications — the `company` filter is silently ignored when `status` is present.
**Root cause:** `JobApplicationService.findAll` uses `if / else if`, so only one filter is applied.
**Fix idea:** a repository method `findByStatusAndCompanyContainingIgnoreCase` or a JPA `Specification`.

---

### BUG-2 · Applied date in the future is accepted
**Severity:** Minor · **Priority:** Medium · **Endpoint:** `POST /api/applications`

**Steps:** `POST` with `"appliedAt": "<today + 30 days>"`
**Expected:** `400 Bad Request`, error on `appliedAt`.
**Actual:** `201 Created` — the funnel statistics can count an application that has not happened.
**Fix idea:** `@PastOrPresent` on `appliedAt` in `JobApplicationRequest`.

---

### BUG-3 · `PUT` without `status` resets the status to `FOUND`
**Severity:** Major · **Priority:** Medium · **Endpoint:** `PUT /api/applications/{id}`

**Steps**
1. Create an application with `"status":"INTERVIEW"`.
2. `PUT` the same id with `{"company":"Acme","position":"QA","notes":"call on Friday"}` (editing only the notes).

**Expected:** status stays `INTERVIEW` (or `400` if `status` is required for `PUT`).
**Actual:** status silently becomes `FOUND`; the interview disappears from the stats.
**Fix idea:** make `status` required in `PUT`, or keep the current value when it is `null`.
