package com.nikitaamoev.jobtracker.dto;

import com.nikitaamoev.jobtracker.model.Status;

import java.util.Map;

/**
 * Статистика воронки.
 * responseRate — доля откликов, на которые ответили (тестовое, интервью, оффер или отказ), в процентах.
 */
public record StatsResponse(long total, Map<Status, Long> byStatus, double responseRate) {
}
