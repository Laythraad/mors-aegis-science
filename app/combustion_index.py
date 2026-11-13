"""Transactional, source-verified SQLite index of NASA combustion table rows."""
import json

from app.bass import experimental_table
from app.cool_flames import DOI as COOL_DOI, source_table as cool_source
from app.flame_design import TABLES, load_flame_table


def load_verified_sources():
    bass = experimental_table()
    sources = [("bass_ii", bass["sha256"], bass["doi"], bass["rows"])]
    for mode in ("normal", "inverse"):
        sources.append(("flame_" + mode, TABLES[mode][1], "https://doi.org/10.60555/w4zy-bt45",
                        load_flame_table(mode)))
        rows, _, digest, _, _ = cool_source(mode)
        sources.append(("cool_" + mode, digest, COOL_DOI, rows))
    return sources


def sync_index(db):
    # Verify every source before changing any index data.
    sources = load_verified_sources()
    db.execute("""CREATE TABLE IF NOT EXISTS combustion_index_sources
               (dataset TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, doi TEXT NOT NULL, indexed_rows INTEGER NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS combustion_index_rows
               (dataset TEXT NOT NULL REFERENCES combustion_index_sources(dataset) ON DELETE CASCADE,
                row_index INTEGER NOT NULL, test_id TEXT NOT NULL, fuel TEXT NOT NULL, source_json TEXT NOT NULL,
                PRIMARY KEY(dataset, row_index))""")
    db.execute("CREATE INDEX IF NOT EXISTS combustion_index_test ON combustion_index_rows(dataset, test_id)")
    db.execute("BEGIN IMMEDIATE")
    for dataset, digest, doi, rows in sources:
        meaningful = [(index, row) for index, row in enumerate(rows)
                      if any(str(value or "").strip() for value in row.values())]
        existing = db.execute("SELECT source_sha256, indexed_rows FROM combustion_index_sources WHERE dataset=?",
                              (dataset,)).fetchone()
        actual = db.execute("SELECT COUNT(*) FROM combustion_index_rows WHERE dataset=?", (dataset,)).fetchone()[0]
        if existing and existing["source_sha256"] == digest and existing["indexed_rows"] == len(meaningful) and actual == len(meaningful):
            continue
        db.execute("DELETE FROM combustion_index_sources WHERE dataset=?", (dataset,))
        db.execute("INSERT INTO combustion_index_sources VALUES (?,?,?,?)", (dataset, digest, doi, len(meaningful)))
        db.executemany("INSERT INTO combustion_index_rows VALUES (?,?,?,?,?)",
                       [(dataset, index, str(row.get("Test") or row.get("Test #") or ""),
                         str(row.get("Fuel") or row.get("Fuel Sample Material") or ""),
                         json.dumps(row, ensure_ascii=False, sort_keys=True))
                        for index, row in meaningful])


def query_index(db, dataset, query, offset, limit):
    sync_index(db)
    clauses, params = [], []
    if dataset:
        clauses.append("r.dataset=?")
        params.append(dataset)
    if query:
        escaped = query.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("(lower(r.test_id) LIKE ? ESCAPE '\\' OR lower(r.fuel) LIKE ? ESCAPE '\\')")
        params.extend(["%" + escaped + "%", "%" + escaped + "%"])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    total = db.execute("SELECT COUNT(*) FROM combustion_index_rows r" + where, params).fetchone()[0]
    result = db.execute("""SELECT r.dataset,r.row_index,r.test_id,r.fuel,r.source_json,
                           s.source_sha256,s.doi FROM combustion_index_rows r
                           JOIN combustion_index_sources s ON s.dataset=r.dataset""" + where +
                        " ORDER BY r.dataset,r.row_index LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
    return {"total": total, "offset": offset, "limit": limit,
            "items": [{"dataset": row["dataset"], "row_index": row["row_index"], "test_id": row["test_id"],
                       "fuel": row["fuel"], "source_row": json.loads(row["source_json"]),
                       "source_sha256": row["source_sha256"], "doi": row["doi"]} for row in result],
            "scope": "Source-verified nonblank rows; exact source fields retained. Configurations remain separate."}
