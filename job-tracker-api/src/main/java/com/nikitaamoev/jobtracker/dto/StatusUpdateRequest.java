package com.nikitaamoev.jobtracker.dto;

import com.nikitaamoev.jobtracker.model.Status;
import jakarta.validation.constraints.NotNull;

public record StatusUpdateRequest(@NotNull Status status) {
}
