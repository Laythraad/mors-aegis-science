"""Read the source-preserved NASA PSI BASS-II experimental table."""
import csv
import hashlib
import io
import math
from pathlib import Path

TABLE = Path(__file__).resolve().parent / "static" / "bass-ii-experiment-table.csv"
EXPECTED_SHA256 = "71e792bf6b5fb5ea620c5dd70fbbac05515992e12aefcf5dff47312caa48c042"
SOURCE = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-25"
DOI = "https://doi.org/10.60555/4qc4-de67"
MEASURES = {
    "oxygen": ("Calibrated  initial O2 % by vol ", "Calibrated final O2 % by vol", "% vol"),
    "carbon_dioxide": ("Initial CO2 % by vol", "Final CO2 % by vol", "% vol"),
    "carbon_monoxide": ("Initial CO (ppm)", "Final CO (ppm)", "ppm"),
}


def finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def experimental_table():
    content = TABLE.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("NASA PSI source table checksum mismatch")
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline="")))
    return {
        "investigation": "PSI-25 BASS-II",
        "source_url": SOURCE,
        "source_filename": "PSI-25_Experimental table_BASS-II.csv",
        "source_version": 1,
        "investigation_version": 4,
        "doi": DOI,
        "license": "CC0-1.0",
        "sha256": digest,
        "rows": rows,
        "limitations": "Experimental table values are reproduced as published. Missing and nonnumeric entries are retained. Differences within a test do not establish causation or direct comparability across tests.",
    }


def compare_tests(first_index: int, second_index: int):
    """Return recorded test conditions and within-test differences where numeric."""
    table = experimental_table()
    rows = table["rows"]
    if first_index == second_index or min(first_index, second_index) < 0 or max(first_index, second_index) >= len(rows):
        raise ValueError("Select two distinct test records")

    selected = []
    for index in (first_index, second_index):
        row = rows[index]
        measures = {}
        for name, (initial_key, final_key, unit) in MEASURES.items():
            initial, final = finite_number(row[initial_key]), finite_number(row[final_key])
            measures[name] = {
                "initial_source": row[initial_key], "final_source": row[final_key],
                "initial": initial, "final": final, "unit": unit,
                "change": round(final - initial, 8) if initial is not None and final is not None else None,
            }
        selected.append({"row_index": index, "investigator": row["PI"], "test": row["Test #"],
                         "date": row["Date"], "sample": row["Fuel Sample Material"],
                         "flow_restrictor": row["Flow restrictor"],
                         "fan_display": row["Fan display"], "air_display": row["Air display"],
                         "measurements": measures, "source_row": row})
    checks = []
    criteria = [
        ("sample_description", "Fuel Sample Material", False),
        ("flow_restrictor", "Flow restrictor", False),
        ("fan_display", "Fan display", False),
        ("air_display", "Air display", False),
        ("initial_oxygen", "Calibrated  initial O2 % by vol ", True),
    ]
    for name, source_field, numeric in criteria:
        raw = [rows[index].get(source_field, "") for index in (first_index, second_index)]
        cleaned = [" ".join(str(value or "").split()) for value in raw]
        if numeric:
            values = [finite_number(value) for value in cleaned]
        else:
            values = [value.casefold() if value.casefold() not in {"", "none", "n/a", "na", "-"} else None
                      for value in cleaned]
        if any(value is None for value in values):
            outcome = "unavailable"
        elif values[0] == values[1]:
            outcome = "same_recorded_value" if numeric else "same_source_text"
        else:
            outcome = "different_recorded_value" if numeric else "different_source_text"
        checks.append({"criterion": name, "source_field": source_field, "values": raw, "outcome": outcome})
    differences = [check["criterion"] for check in checks if check["outcome"].startswith("different")]
    unavailable = [check["criterion"] for check in checks if check["outcome"] == "unavailable"]
    condition_status = ("recorded_differences" if differences else
                        "incomplete_metadata" if unavailable else "no_recorded_differences")
    return {
        "question": "What values and conditions were recorded for the two selected BASS-II tests?",
        "source_url": table["source_url"], "source_filename": table["source_filename"],
        "source_version": table["source_version"], "sha256": table["sha256"],
        "doi": DOI,
        "method": "Initial-to-final difference within each test equals final minus initial, in the original unit.",
        "tests": selected,
        "comparability": "unverified",
        "condition_status": condition_status,
        "different_recorded_criteria": differences,
        "unavailable_criteria": unavailable,
        "comparison_scope": "Side-by-side source values and within-test changes only; no matched-condition or causal comparison is established.",
        "condition_checks": checks,
        "condition_check_note": "Text checks compare recorded labels after whitespace and case normalization, not physical equivalence. Different wording may describe the same material; matching text does not prove matched experimental conditions.",
        "limitations": [
            "Conditions and fuels may differ; published labels alone do not establish matching apparatus settings.",
            "Time-resolved sensor data, calibration uncertainty and sampling details are not provided in this table.",
            "Within-test differences are descriptive; they do not establish causation or flame temperature.",
            "Blank and nonnumeric source entries are unavailable and never treated as zero.",
        ],
        "reproducibility": {"source_sha256": table["sha256"], "source_version": table["source_version"],
                            "row_indices_zero_based": [first_index, second_index],
                            "method_version": "bass-ii-paired-values-v3"},
    }


def field_overview(measure: str):
    """Return all paired, finite source entries, preserving source row identity."""
    if measure not in MEASURES:
        raise ValueError("Unknown measurement")
    table = experimental_table()
    initial_key, final_key, unit = MEASURES[measure]
    pairs = []
    initial_count = final_count = 0
    for index, row in enumerate(table["rows"]):
        initial = finite_number(row[initial_key])
        final = finite_number(row[final_key])
        initial_count += initial is not None
        final_count += final is not None
        if initial is not None and final is not None:
            pairs.append({"row_index": index, "test": row["Test #"], "investigator": row["PI"],
                          "date": row["Date"], "fuel": row["Fuel Sample Material"],
                          "initial": initial, "final": final})
    return {"measure": measure, "unit": unit, "total": len(table["rows"]),
            "initial_count": initial_count, "final_count": final_count,
            "paired_count": len(pairs), "pairs": pairs, "doi": DOI,
            "source_url": SOURCE, "source_sha256": table["sha256"],
            "method": "Finite numeric initial and final entries only. No imputation, outlier removal or causal inference.",
            "limitations": "Records have different test conditions. Entries may include instrument offsets or transcription issues. Calibration uncertainty and complete time series are not supplied."}
