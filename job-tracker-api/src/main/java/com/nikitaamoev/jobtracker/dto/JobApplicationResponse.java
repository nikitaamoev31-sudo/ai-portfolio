package com.nikitaamoev.jobtracker.dto;

import com.nikitaamoev.jobtracker.model.JobApplication;
import com.nikitaamoev.jobtracker.model.Status;

import java.time.LocalDate;
import java.time.LocalDateTime;

public record JobApplicationResponse(
        Long id,
        String company,
        String position,
        String url,
        Integer salaryUsd,
        Status status,
        LocalDate appliedAt,
        String notes,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
    public static JobApplicationResponse from(JobApplication a) {
        return new JobApplicationResponse(
                a.getId(), a.getCompany(), a.getPosition(), a.getUrl(), a.getSalaryUsd(),
                a.getStatus(), a.getAppliedAt(), a.getNotes(), a.getCreatedAt(), a.getUpdatedAt());
    }
}
