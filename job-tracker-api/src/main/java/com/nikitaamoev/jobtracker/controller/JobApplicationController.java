package com.nikitaamoev.jobtracker.controller;

import com.nikitaamoev.jobtracker.dto.JobApplicationRequest;
import com.nikitaamoev.jobtracker.dto.JobApplicationResponse;
import com.nikitaamoev.jobtracker.dto.StatsResponse;
import com.nikitaamoev.jobtracker.dto.StatusUpdateRequest;
import com.nikitaamoev.jobtracker.model.Status;
import com.nikitaamoev.jobtracker.service.JobApplicationService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/applications")
public class JobApplicationController {

    private final JobApplicationService service;

    public JobApplicationController(JobApplicationService service) {
        this.service = service;
    }

    @GetMapping
    public Page<JobApplicationResponse> list(
            @RequestParam(required = false) Status status,
            @RequestParam(required = false) String company,
            @PageableDefault(size = 20, sort = "createdAt", direction = Sort.Direction.DESC) Pageable pageable) {
        return service.findAll(status, company, pageable);
    }

    @GetMapping("/{id}")
    public JobApplicationResponse get(@PathVariable Long id) {
        return service.findById(id);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public JobApplicationResponse create(@Valid @RequestBody JobApplicationRequest request) {
        return service.create(request);
    }

    @PutMapping("/{id}")
    public JobApplicationResponse update(@PathVariable Long id, @Valid @RequestBody JobApplicationRequest request) {
        return service.update(id, request);
    }

    @PatchMapping("/{id}/status")
    public JobApplicationResponse changeStatus(@PathVariable Long id, @Valid @RequestBody StatusUpdateRequest request) {
        return service.changeStatus(id, request.status());
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Long id) {
        service.delete(id);
    }

    @GetMapping("/stats")
    public StatsResponse stats() {
        return service.stats();
    }
}
