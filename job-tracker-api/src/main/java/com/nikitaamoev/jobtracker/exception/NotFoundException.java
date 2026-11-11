package com.nikitaamoev.jobtracker.exception;

public class NotFoundException extends RuntimeException {
    public NotFoundException(Long id) {
        super("Job application " + id + " not found");
    }
}
