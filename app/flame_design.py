"""NASA PSI-10 Flame Design source tables and descriptive plotting data."""
import csv
import hashlib
import io
from pathlib import Path

from app.bass import finite_number

ROOT = Path(__file__).resolve().parent / "static"
TABLES = {
    "normal": ("psi-10-normal.csv", "4a663292bd3f65201943cc71bd661a70383639276a9176f64105b285bf0b6deb"),
    "inverse": ("psi-10-inverse.csv", "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4"),
}
ORIGINAL_NAMES = {
    "normal": "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
    "inverse": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
}


def load_flame_table(configuration):
    if configuration not in TABLES:
        raise ValueError("Unknown flame configuration")
    filename, checksum = TABLES[configuration]
    content = (ROOT / filename).read_bytes()
    if hashlib.sha256(content).hexdigest() != checksum:
        raise RuntimeError("Flame Design source table checksum mismatch")
    return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline="")))


def flame_design_overview(configuration):
    rows = load_flame_table(configuration)
    filename, checksum = TABLES[configuration]
    pairs = []
    for index, row in enumerate(rows):
        flow = finite_number(row.get("mtot (mg/s)"))
        pressure = finite_number(row.get("pmean (atm)"))
        if flow is not None and pressure is not None:
            pairs.append({"row_index": index, "test": row["Test"], "day": row["Day"],
                          "flow_mg_s": flow, "pressure_atm": pressure, "source_row": row})
    return {"investigation": "PSI-10 ACME Flame Design", "configuration": configuration,
            "doi": "https://doi.org/10.60555/w4zy-bt45",
            "source_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-10",
            "source_filename": filename, "original_filename": ORIGINAL_NAMES[configuration], "source_version": 1,
            "source_sha256": checksum, "records": len(rows), "paired_count": len(pairs), "pairs": pairs,
            "method": "Plot finite numeric mtot (mg/s) against pmean (atm), as recorded in the source table.",
            "limitations": "Normal and inverse flame tables remain separate. Conditions vary between tests; an association does not establish causation. Measurement uncertainty is not supplied in the source table."}


def flame_design_records(configuration, query, offset, limit):
    rows = load_flame_table(configuration)
    term = query.casefold().strip()
    matches = [(index, row) for index, row in enumerate(rows)
               if not term or any(term in str(value or "").casefold() for value in row.values())]
    return {"configuration": configuration, "total": len(matches), "offset": offset, "limit": limit,
            "items": [{"row_index": index, "source_row": row} for index, row in matches[offset:offset + limit]],
            "source_sha256": TABLES[configuration][1],
            "source_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-10"}
