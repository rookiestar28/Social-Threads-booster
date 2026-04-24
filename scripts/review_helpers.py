#!/usr/bin/env python3
"""
Deterministic helpers for /review prediction comparison and review-state updates.
"""

from __future__ import annotations

from typing import Any

import prediction_helpers
import tracker_utils


def _band_hit(actual: float, conservative: float, optimistic: float) -> str:
    if actual < conservative:
        return "Under"
    if actual > optimistic:
        return "Over"
    return "In"


def _deviation_pct(actual: float, baseline: float) -> float | None:
    if baseline == 0:
        return None
    return round(((actual - baseline) / baseline) * 100, 2)


def build_prediction_comparison(prediction_snapshot: dict, actual_metrics: dict[str, Any]) -> list[dict]:
    prediction_helpers.validate_prediction_snapshot(prediction_snapshot)
    rows = []
    for metric in prediction_helpers.PREDICTED_METRICS:
        band = prediction_snapshot["ranges"][metric]
        actual = actual_metrics.get(metric, 0)
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            actual = 0
        rows.append(
            {
                "metric": metric,
                "conservative": band["conservative"],
                "baseline": band["baseline"],
                "optimistic": band["optimistic"],
                "actual": actual,
                "band_hit": _band_hit(actual, band["conservative"], band["optimistic"]),
                "deviation_vs_baseline_pct": _deviation_pct(actual, band["baseline"]),
            }
        )
    return rows


def _format_deviation(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value}%"


def render_prediction_comparison_table(comparison_rows: list[dict]) -> str:
    lines = [
        "| Metric | Conservative | Baseline | Optimistic | Actual | Band hit? | Deviation vs baseline |",
        "|--------|--------------|----------|------------|--------|-----------|-----------------------|",
    ]
    for row in comparison_rows:
        metric = str(row["metric"]).capitalize()
        lines.append(
            f"| {metric} | {row['conservative']} | {row['baseline']} | {row['optimistic']} | "
            f"{row['actual']} | {row['band_hit']} | {_format_deviation(row['deviation_vs_baseline_pct'])} |"
        )
    return "\n".join(lines)


def apply_review_state_update(
    post: dict,
    *,
    checkpoint_hours: int | float,
    deviation_summary: str,
    calibration_notes: list[str] | None = None,
    now: str | None = None,
) -> None:
    review_state = post.setdefault("review_state", tracker_utils.build_review_state())
    defaults = tracker_utils.build_review_state()
    for key, value in defaults.items():
        if key not in review_state:
            review_state[key] = value
    review_state["last_reviewed_at"] = now or tracker_utils.utc_now_iso()
    review_state["actual_checkpoint_hours"] = checkpoint_hours
    review_state["deviation_summary"] = deviation_summary
    review_state["calibration_notes"] = list(calibration_notes or [])
