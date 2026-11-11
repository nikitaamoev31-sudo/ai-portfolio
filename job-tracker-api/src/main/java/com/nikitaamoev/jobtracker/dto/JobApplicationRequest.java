package com.nikitaamoev.jobtracker.dto;

import com.nikitaamoev.jobtracker.model.Status;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

import java.time.LocalDate;

public record JobApplicationRequest(
        @NotBlank @Size(max = 255) String company,
        @NotBlank @Size(max = 255) String position,
        @Size(max = 500) String url,
        @PositiveOrZero Integer salaryUsd,
        Status status,
        LocalDate appliedAt,
        @Size(max = 2000) String notes
) {
}
