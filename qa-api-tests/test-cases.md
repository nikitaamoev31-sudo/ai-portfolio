# Test cases — job-tracker-api

| ID | Area | Case | Expected | Automated |
|---|---|---|---|---|
| TC-01 | Create | Valid body without status | 201, `status = FOUND`, `appliedAt = null` | `test_create_returns_201_with_defaults` |
| TC-02 | Read | Get by id | 200, same field values | `test_get_by_id_returns_same_record` |
| TC-03 | Update | PUT full body | 200, fields replaced | `test_put_replaces_fields` |
| TC-04 | Status | PATCH → APPLIED, no date | `appliedAt = today` | `test_patch_to_applied_sets_today_as_applied_date` |
| TC-05 | Status | PATCH → APPLIED, date set | date unchanged | `test_patch_keeps_existing_applied_date` |
| TC-06 | Delete | Delete, then get | 204, then 404 | `test_delete_returns_204_and_record_is_gone` |
| TC-07 | List | Filter by status | only that status | `test_filter_by_status` |
| TC-08 | List | Filter by company, other case | case-insensitive match | `test_filter_by_company_is_case_insensitive` |
| TC-09 | List | 3 records, page size 2 | 2 + 1 items, total 3 | `test_pagination` |
| TC-10 | Stats | Add 2 records | counters grow by 2, all 6 statuses present | `test_stats_count_new_records` |
| TC-11 | Validation | Missing / blank company, missing position | 400 + field error | `test_invalid_body_returns_400_with_field_error` |
| TC-12 | Validation | Negative salary, company > 255, notes > 2000 | 400 + field error | same, parametrized |
| TC-13 | Validation | Unknown status `HIRED` | 400 | `test_unknown_status_value_is_rejected` |
| TC-14 | Validation | PATCH with empty body | 400 | `test_patch_without_status_is_rejected` |
| TC-15 | Errors | Malformed JSON | 400 | `test_malformed_json_returns_400` |
| TC-16 | Errors | GET / DELETE unknown id | 404 with problem detail | `test_unknown_id_returns_404_problem_detail` |
| TC-17 | Errors | `?status=nope` | 400, not 500 | `test_unknown_status_filter_returns_400_not_500` |
| TC-18 | List | Status + company together | both filters apply | ❌ BUG-1 |
| TC-19 | Validation | Applied date in the future | 400 | ❌ BUG-2 |
| TC-20 | Update | PUT without status | status kept | ❌ BUG-3 |
