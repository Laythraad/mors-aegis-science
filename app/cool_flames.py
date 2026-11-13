"""Source-preserving NASA PSI-159 CFI-G experiment tables."""
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from statistics import median

from app.bass import finite_number

ROOT = Path(__file__).resolve().parent / "static"
SOURCES = {
    "normal": ("psi-159-normal.csv", "d95a621c3fbd27d204dd32ed29fa17d68f2b779d6a523cde8479ed7ebaa5251a",
               "PSI-159_Experimental table_CFI-G_Normal Flames.csv", "Peak burner T (C )"),
    "inverse": ("psi-159-inverse.csv", "d4d44f8b9896936728748e34d1b6ad0812032a92fa5289599b708c138e3a9b39",
                "PSI-159_Experimental table_CFI-G_Inverse Flames.csv", "Peak burner Temp (C)"),
}
DOI = "https://doi.org/10.60555/cyt1-kh64"


def duration_distribution(selected):
    """Bin all finite recorded durations, independently of temperature availability."""
    values = [(index, value) for index, row in selected
              if (value := finite_number(row.get("burn time (sec)"))) is not None]
    if not values:
        return {"count": 0, "missing_or_nonnumeric": len(selected), "median_s": None, "bins": []}
    low, high = min(v for _, v in values), max(v for _, v in values)
    # A degenerate distribution is one inclusive bin; otherwise use six equal-width bins.
    count = 1 if low == high else 6
    width = (high - low) / count if count > 1 else 0
    bins = [{"lower_s": low + i * width, "upper_s": low + (i + 1) * width,
             "upper_inclusive": i == count - 1, "row_indices": []} for i in range(count)]
    for index, value in values:
        position = min(count - 1, int((value - low) / width)) if width else 0
        bins[position]["row_indices"].append(index)
    for item in bins:
        item["count"] = len(item["row_indices"])
    return {"count": len(values), "missing_or_nonnumeric": len(selected) - len(values),
            "median_s": median(v for _, v in values), "bins": bins}


def source_table(configuration):
    if configuration not in SOURCES:
        raise ValueError("Unknown flame configuration")
    filename, checksum, original_name, temperature_field = SOURCES[configuration]
    content = (ROOT / filename).read_bytes()
    if hashlib.sha256(content).hexdigest() != checksum:
        raise RuntimeError("CFI-G source checksum mismatch")
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline="")))
    return rows, filename, checksum, original_name, temperature_field


def overview(configuration, fuel=""):
    rows, filename, checksum, original_name, temperature_field = source_table(configuration)
    meaningful = [(index, row) for index, row in enumerate(rows)
                  if any(str(value or "").strip() for value in row.values())]
    fuel_options = sorted({row["Fuel"].strip() for _, row in meaningful if row["Fuel"].strip()})
    if fuel and fuel not in fuel_options:
        raise ValueError("Unknown fuel")
    selected = [(index, row) for index, row in meaningful if not fuel or row["Fuel"].strip() == fuel]
    pairs = []
    for index, row in selected:
        burn_time = finite_number(row.get("burn time (sec)"))
        burner_temperature = finite_number(row.get(temperature_field))
        if burn_time is not None and burner_temperature is not None:
            pairs.append({"row_index": index, "test": row["Test"], "fuel": row["Fuel"],
                          "burn_time_s": burn_time, "peak_burner_c": burner_temperature,
                          "source_row": row})
    ignition = Counter(row.get("Hot ignition", "").strip() or "(blank)" for _, row in selected)
    result = {"investigation": "NASA PSI-159 ACME CFI-G", "configuration": configuration,
            "doi": DOI, "source_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-159",
            "source_filename": filename, "original_filename": original_name, "source_version": 1,
            "source_sha256": checksum, "records": len(rows), "nonempty_records": len(meaningful),
            "blank_rows": len(rows) - len(meaningful), "selected_records": len(selected),
            "fuel": fuel, "fuel_options": fuel_options,
            "selected_source_rows": [{"row_index": index, "source_row": row} for index, row in selected],
            "hot_ignition_categories": [{"source_value": value, "count": count}
                                        for value, count in sorted(ignition.items())],
            "duration_distribution": duration_distribution(selected),
            "paired_count": len(pairs), "pairs": pairs,
            "method": "Plot finite numeric burn time (s) against the source field peak burner temperature (°C).",
            "limitations": "Burner temperature is not flame temperature. Normal and inverse tables are separate. Records include failed ignitions and zero burn durations. Test conditions vary and measurement uncertainty is not supplied in these tables. Completely blank CSV rows are excluded from the test summary but retained in the source file.",
            "reproducibility": {"method_version": "cfi-g-descriptive-v2", "source_sha256": checksum,
                                "configuration": configuration, "fuel_filter_exact": fuel,
                                "cleaning": "Exclude fully blank rows; retain exact labels. Scatter uses finite numeric pairs. Duration distribution uses all finite durations, including zeros; six equal-width bins with an inclusive last edge."}}
    canonical = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    result["analysis_sha256"] = hashlib.sha256(canonical).hexdigest()
    return result
