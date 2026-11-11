package com.nikitaamoev.jobtracker.model;

/** Этапы воронки отклика на вакансию. */
public enum Status {
    FOUND,
    APPLIED,
    TEST_TASK,
    INTERVIEW,
    OFFER,
    REJECTED
}
