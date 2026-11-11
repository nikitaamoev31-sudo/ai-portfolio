package com.nikitaamoev.jobtracker.repository;

import com.nikitaamoev.jobtracker.model.JobApplication;
import com.nikitaamoev.jobtracker.model.Status;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface JobApplicationRepository extends JpaRepository<JobApplication, Long> {

    Page<JobApplication> findByStatus(Status status, Pageable pageable);

    Page<JobApplication> findByCompanyContainingIgnoreCase(String company, Pageable pageable);

    /** Возвращает пары [status, count] для статистики воронки. */
    @Query("select a.status, count(a) from JobApplication a group by a.status")
    List<Object[]> countByStatus();
}
