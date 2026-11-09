"""Read the source-preserved NASA PSI BASS-II experimental table."""
import csv
import hashlib
import io
from pathlib import Path

TABLE = Path(__file__).resolve().parent / "static" / "bass-ii-experiment-table.csv"
EXPECTED_SHA256 = "71e792bf6b5fb5ea620c5dd70fbbac05515992e12aefcf5dff47312caa48c042"
SOURCE = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-25"


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
        "sha256": digest,
        "rows": rows,
        "limitations": "Experimental table values are reproduced as published. Missing and nonnumeric entries are retained. Differences within a test do not establish causation or direct comparability across tests.",
    }
