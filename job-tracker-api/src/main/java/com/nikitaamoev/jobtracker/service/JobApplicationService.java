package com.nikitaamoev.jobtracker.service;

import com.nikitaamoev.jobtracker.dto.JobApplicationRequest;
import com.nikitaamoev.jobtracker.dto.JobApplicationResponse;
import com.nikitaamoev.jobtracker.dto.StatsResponse;
import com.nikitaamoev.jobtracker.exception.NotFoundException;
import com.nikitaamoev.jobtracker.model.JobApplication;
import com.nikitaamoev.jobtracker.model.Status;
import com.nikitaamoev.jobtracker.repository.JobApplicationRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.EnumMap;
import java.util.Map;
import java.util.Set;

@Service
@Transactional(readOnly = true)
public class JobApplicationService {

    private static final Set<Status> GOT_RESPONSE =
            Set.of(Status.TEST_TASK, Status.INTERVIEW, Status.OFFER, Status.REJECTED);

    private final JobApplicationRepository repository;

    public JobApplicationService(JobApplicationRepository repository) {
        this.repository = repository;
    }

    public Page<JobApplicationResponse> findAll(Status status, String company, Pageable pageable) {
        Page<JobApplication> page;
        if (status != null) {
            page = repository.findByStatus(status, pageable);
        } else if (company != null && !company.isBlank()) {
            page = repository.findByCompanyContainingIgnoreCase(company, pageable);
        } else {
            page = repository.findAll(pageable);
        }
        return page.map(JobApplicationResponse::from);
    }

    public JobApplicationResponse findById(Long id) {
        return JobApplicationResponse.from(getOrThrow(id));
    }

    @Transactional
    public JobApplicationResponse create(JobApplicationRequest request) {
        JobApplication entity = new JobApplication();
        apply(entity, request);
        return JobApplicationResponse.from(repository.save(entity));
    }

    @Transactional
    public JobApplicationResponse update(Long id, JobApplicationRequest request) {
        JobApplication entity = getOrThrow(id);
        apply(entity, request);
        return JobApplicationResponse.from(repository.save(entity));
    }

    /** Меняет статус; при переходе в APPLIED сам проставляет дату отклика. */
    @Transactional
    public JobApplicationResponse changeStatus(Long id, Status status) {
        JobApplication entity = getOrThrow(id);
        entity.setStatus(status);
        if (status == Status.APPLIED && entity.getAppliedAt() == null) {
            entity.setAppliedAt(LocalDate.now());
        }
        return JobApplicationResponse.from(repository.save(entity));
    }

    @Transactional
    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw new NotFoundException(id);
        }
        repository.deleteById(id);
    }

    public StatsResponse stats() {
        Map<Status, Long> byStatus = new EnumMap<>(Status.class);
        for (Status s : Status.values()) {
            byStatus.put(s, 0L);
        }
        for (Object[] row : repository.countByStatus()) {
            byStatus.put((Status) row[0], (Long) row[1]);
        }
        long total = byStatus.values().stream().mapToLong(Long::longValue).sum();
        long sent = total - byStatus.get(Status.FOUND);
        long responded = GOT_RESPONSE.stream().mapToLong(byStatus::get).sum();
        double rate = sent == 0 ? 0.0 : Math.round(responded * 1000.0 / sent) / 10.0;
        return new StatsResponse(total, byStatus, rate);
    }

    private JobApplication getOrThrow(Long id) {
        return repository.findById(id).orElseThrow(() -> new NotFoundException(id));
    }

    private void apply(JobApplication entity, JobApplicationRequest r) {
        entity.setCompany(r.company());
        entity.setPosition(r.position());
        entity.setUrl(r.url());
        entity.setSalaryUsd(r.salaryUsd());
        entity.setStatus(r.status() != null ? r.status() : Status.FOUND);
        entity.setAppliedAt(r.appliedAt());
        entity.setNotes(r.notes());
    }
}
