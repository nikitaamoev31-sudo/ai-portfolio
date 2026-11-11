package com.nikitaamoev.jobtracker.service;

import com.nikitaamoev.jobtracker.dto.JobApplicationRequest;
import com.nikitaamoev.jobtracker.dto.JobApplicationResponse;
import com.nikitaamoev.jobtracker.dto.StatsResponse;
import com.nikitaamoev.jobtracker.exception.NotFoundException;
import com.nikitaamoev.jobtracker.model.JobApplication;
import com.nikitaamoev.jobtracker.model.Status;
import com.nikitaamoev.jobtracker.repository.JobApplicationRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class JobApplicationServiceTest {

    @Mock
    private JobApplicationRepository repository;

    @InjectMocks
    private JobApplicationService service;

    @Test
    void createUsesFoundStatusByDefault() {
        when(repository.save(any(JobApplication.class))).thenAnswer(inv -> inv.getArgument(0));

        JobApplicationResponse result = service.create(
                new JobApplicationRequest("Acme", "AI Automation Engineer", null, 1000, null, null, null));

        assertThat(result.status()).isEqualTo(Status.FOUND);
        assertThat(result.company()).isEqualTo("Acme");
    }

    @Test
    void changeStatusToAppliedSetsAppliedDate() {
        JobApplication existing = new JobApplication();
        existing.setCompany("Acme");
        existing.setPosition("Junior Java Developer");
        when(repository.findById(1L)).thenReturn(Optional.of(existing));
        when(repository.save(any(JobApplication.class))).thenAnswer(inv -> inv.getArgument(0));

        JobApplicationResponse result = service.changeStatus(1L, Status.APPLIED);

        assertThat(result.status()).isEqualTo(Status.APPLIED);
        assertThat(result.appliedAt()).isEqualTo(LocalDate.now());
    }

    @Test
    void findByIdThrowsWhenMissing() {
        when(repository.findById(42L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.findById(42L)).isInstanceOf(NotFoundException.class);
    }

    @Test
    void statsCalculatesResponseRate() {
        when(repository.countByStatus()).thenReturn(List.of(
                new Object[]{Status.FOUND, 5L},
                new Object[]{Status.APPLIED, 6L},
                new Object[]{Status.INTERVIEW, 3L},
                new Object[]{Status.REJECTED, 1L}));

        StatsResponse stats = service.stats();

        assertThat(stats.total()).isEqualTo(15);
        // отправлено 10 (всё, кроме FOUND), ответили 4 -> 40%
        assertThat(stats.responseRate()).isEqualTo(40.0);
        assertThat(stats.byStatus().get(Status.OFFER)).isZero();
    }
}
