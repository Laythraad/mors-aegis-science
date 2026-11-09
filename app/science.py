"""Deterministic, provenance-preserving CSV time-series ingestion and audit."""
from __future__ import annotations

import csv
import hashlib
import io
import math
import statistics
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLUMNS = 32
MAX_FIELD_CHARS = 512
ALLOWED_COLUMNS = {"timestamp", "value", "unit", "experiment_id", "sensor", "source"}


class DatasetValidationError(ValueError):
    pass


def _parse_time(value: str, row_number: int) -> datetime:
    raw = value.strip()
    if not raw:
        raise DatasetValidationError(f"CSV row {row_number}: timestamp is required")
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DatasetValidationError(f"CSV row {row_number}: timestamp must be ISO-8601") from exc
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def analyze_csv_timeseries(content: bytes) -> dict[str, Any]:
    if not content:
        raise DatasetValidationError("CSV file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise DatasetValidationError(f"CSV exceeds {MAX_UPLOAD_BYTES} byte limit")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DatasetValidationError("CSV must be UTF-8 encoded") from exc
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames or []
        if len(headers) > MAX_COLUMNS:
            raise DatasetValidationError(f"CSV may contain at most {MAX_COLUMNS} columns")
        normalized = [h.strip().lower() for h in headers]
        if any(len(h) > 64 for h in headers):
            raise DatasetValidationError("CSV header exceeds 64 characters")
        if len(normalized) != len(set(normalized)):
            raise DatasetValidationError("CSV column names must be unique")
        unknown = sorted(set(normalized) - ALLOWED_COLUMNS)
        if unknown:
            raise DatasetValidationError(f"Unsupported CSV columns: {', '.join(unknown)}")
        if not {"timestamp", "value"}.issubset(normalized):
            raise DatasetValidationError("CSV requires timestamp and value columns")
        rows: list[dict[str, Any]] = []
        missing_values = 0
        units: set[str] = set()
        for line, raw in enumerate(reader, start=2):
            if len(rows) + missing_values >= MAX_ROWS:
                raise DatasetValidationError(f"CSV exceeds {MAX_ROWS} data rows")
            if None in raw or any(value is None for value in raw.values()):
                raise DatasetValidationError(f"CSV row {line}: number of fields does not match the header")
            if any(len(value) > MAX_FIELD_CHARS for value in raw.values()):
                raise DatasetValidationError(f"CSV row {line}: field exceeds {MAX_FIELD_CHARS} characters")
            row = {key.strip().lower(): (value or "").strip() for key, value in raw.items() if key is not None}
            timestamp = _parse_time(row.get("timestamp", ""), line)
            unit = row.get("unit", "")
            if unit:
                units.add(unit)
            raw_value = row.get("value", "")
            if not raw_value:
                missing_values += 1
                continue
            try:
                value = float(raw_value)
            except ValueError as exc:
                raise DatasetValidationError(f"CSV row {line}: value must be numeric or blank") from exc
            if not math.isfinite(value):
                raise DatasetValidationError(f"CSV row {line}: value must be finite")
            rows.append({"timestamp": timestamp, "value": value, "unit": unit,
                         "experiment_id": row.get("experiment_id") or None,
                         "sensor": row.get("sensor") or None,
                         "source": row.get("source") or None})
        if len(rows) < 3:
            raise DatasetValidationError("At least three numeric observations are required")
        if len(units) > 1:
            raise DatasetValidationError("Mixed units are not comparable; upload one unit per file")
        rows.sort(key=lambda row: row["timestamp"])
        experiment_ids = sorted({row["experiment_id"] for row in rows if row["experiment_id"]})
        sensors = sorted({row["sensor"] for row in rows if row["sensor"]})
        source_values = sorted({row["source"] for row in rows if row["source"]})
        if len(experiment_ids) > 1 or len(sensors) > 1 or len(source_values) > 1:
            raise DatasetValidationError("A single analysis must contain one experiment_id, sensor, and source; partition mixed series first")
        times = [row["timestamp"] for row in rows]
        values = [row["value"] for row in rows]
        duplicate_timestamps = len(times) - len(set(times))
        if times[0] == times[-1]:
            raise DatasetValidationError("Timestamps must span a nonzero time interval")

        origin = times[0]
        seconds = [(t - origin).total_seconds() for t in times]
        mean_t = statistics.fmean(seconds)
        mean_y = statistics.fmean(values)
        denominator = sum((x - mean_t) ** 2 for x in seconds)
        slope_per_second = sum((x - mean_t) * (y - mean_y) for x, y in zip(seconds, values)) / denominator
        median = statistics.median(values)
        mad = statistics.median(abs(value - median) for value in values)
        if mad > 0:
            robust_z = [0.67448975 * (value - median) / mad for value in values]
            anomaly_indices = [i for i, score in enumerate(robust_z) if abs(score) > 3.5]
            anomaly_method = "Hampel-style modified z score; threshold |z| > 3.5; median absolute deviation"
        else:
            robust_z = [None for _ in values]
            anomaly_indices = []
            anomaly_method = "Not applied: median absolute deviation is zero; no anomalies asserted"
        return {
            "analysis_id": str(uuid.uuid4()), "method": "Deterministic ordinary least-squares linear trend + robust MAD screening",
            "method_version": "timeseries-mad-v1", "evidence_class": "COMPUTED RESULTS",
            "input_classification": "USER-UPLOADED DATA; original source not independently verified",
            "n_rows": len(rows), "missing_value_rows": missing_values,
            "duplicate_timestamp_rows": duplicate_timestamps,
            "time_range": {"start": times[0].isoformat(), "end": times[-1].isoformat(),
                           "duration_seconds": seconds[-1] - seconds[0]},
            "unit": next(iter(units), None),
            "experimental_metadata": {"experiment_id": experiment_ids[0] if experiment_ids else None,
                                       "sensor": sensors[0] if sensors else None,
                                       "declared_source": source_values[0] if source_values else None},
            "statistics": {
                "mean": mean_y, "median": median, "standard_deviation_sample": statistics.stdev(values),
                "minimum": min(values), "maximum": max(values), "trend_slope_per_second": slope_per_second,
                "trend_slope_unit": f"{next(iter(units), 'value')} / second"},
            "anomalies": [{"row_index": i, "timestamp": times[i].isoformat(), "value": values[i],
                           "modified_z_score": robust_z[i], "method": anomaly_method} for i in anomaly_indices],
            "anomaly_method": anomaly_method,
            "time_series": [{"timestamp": t.isoformat(), "value": v, "row_index": i}
                            for i, (t, v) in enumerate(zip(times, values))],
            "validation": {"status": "passed_with_flags" if missing_values or duplicate_timestamps else "passed",
                           "checks": {"utf8_csv": True, "required_columns": True, "finite_numeric_values": True,
                                      "minimum_numeric_rows": True, "single_unit": True,
                                      "missing_value_rows": missing_values,
                                      "duplicate_timestamps": duplicate_timestamps,
                                      "measurement_calibration": "not provided or assessed",
                                      "source_authenticity": "not verified"}},
            "uncertainty": "No instrument uncertainty, calibration, sampling design, or experimental metadata was supplied; none is inferred.",
            "limitations": ["User-uploaded records are not automatically NASA data.",
                            "Trend and anomaly screening are descriptive, not causal or predictive.",
                            "Timestamp duplicates are reported and retained; they may bias summary statistics.",
                            "No physical comparability is established without apparatus, units, calibration, and experiment conditions."],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    except csv.Error as exc:
        raise DatasetValidationError(f"Malformed CSV: {exc}") from exc


def persist_analysis(upload_dir: Path, filename: str, content: bytes, result: dict[str, Any]) -> dict[str, Any]:
    dataset_id = "DS-" + str(uuid.uuid4())
    digest = hashlib.sha256(content).hexdigest()
    safe_name = Path(filename or "timeseries.csv").name
    if not safe_name.lower().endswith(".csv"):
        raise DatasetValidationError("Upload filename must end in .csv")
    stored_name = f"{digest}.csv"
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / stored_name
    result["dataset_id"] = dataset_id
    result["dataset_sha256"] = digest
    result["source_filename"] = safe_name
    result["provenance"] = {"source": "User-uploaded file; not verified as NASA or experimental data",
                            "dataset_id": dataset_id, "dataset_version": "sha256:" + digest,
                            "source_filename": safe_name, "format": "text/csv", "units": result["unit"],
                            "observation_time_range": result["time_range"],
                            "processing_pipeline": ["upload validation", "ISO-8601 timestamp normalization to UTC",
                                                    "numeric and unit validation", "time-series statistics",
                                                    "MAD anomaly screening", "deterministic verification"],
                            "analysis_method": result["method"], "operator": "authenticated local upload",
                            "created_at": result["created_at"]}
    stages = [
        {"stage": "data_acquisition", "status": "completed", "agent": "CSV acquisition/validation", "checks": ["UTF-8", "file size", "required schema", "finite values", "unit consistency"]},
        {"stage": "scientific_analysis", "status": "completed", "agent": "Deterministic time-series engine", "method": result["method"]},
        {"stage": "evidence_verification", "status": "completed", "agent": "Deterministic verification", "source_verified": False},
        {"stage": "scientific_review_council", "status": "not_run", "reason": "No independent domain review model configured"},
    ]
    original_rows = result["time_series"]
    values = [float(row["value"]) for row in original_rows]
    independently_recomputed_mean = statistics.fmean(values)
    mean_matches = math.isclose(independently_recomputed_mean, result["statistics"]["mean"], rel_tol=1e-12, abs_tol=1e-12)
    numeric_metrics = [value for key, value in result["statistics"].items() if key != "trend_slope_unit"]
    finite_outputs = all(math.isfinite(float(value)) for value in numeric_metrics)
    result["validation"]["deterministic_verification"] = {
        "status": "passed" if mean_matches and finite_outputs and len(original_rows) == result["n_rows"] else "failed",
        "checks": {"row_count_matches": len(original_rows) == result["n_rows"],
                   "mean_recomputed_with_fmean": mean_matches,
                   "all_summary_metrics_finite": finite_outputs,
                   "trend_time_span_nonzero": result["time_range"]["duration_seconds"] > 0},
        "scientific_domain_review": "not performed"}
    if result["validation"]["deterministic_verification"]["status"] != "passed":
        raise DatasetValidationError("Deterministic verification failed")
    if not destination.exists():
        destination.write_bytes(content)
    result["provenance"]["validation_status"] = result["validation"]["deterministic_verification"]["status"]
    stages[2]["result"] = result["validation"]["deterministic_verification"]["status"]
    result["pipeline_stages"] = stages
    return {"dataset_id": dataset_id, "stored_filename": stored_name, "source_filename": safe_name,
            "sha256": digest, "result": result, "created_at": result["created_at"]}
