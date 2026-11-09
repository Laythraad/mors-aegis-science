"""Read-only scientific catalog queries over the normalized, source-hashed index."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import HTTPException

DB_PATH = Path(__import__("os").getenv(
    "AEGIS_SCIENCE_CATALOG_DB",
    Path(__file__).resolve().parent.parent / "outputs" / "01a1ad99-40be-7221-9b19-3844f79959e9" / "MORS_Science_Catalog.sqlite",
))
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRODUCTS = {"VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "MODIS_NRT", "VIIRS_SNPP_NRT"}


def connect_catalog() -> sqlite3.Connection:
    if not DB_PATH.is_file():
        raise HTTPException(status_code=503, detail="The local normalized science catalog is unavailable.")
    connection = sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True, timeout=4)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA busy_timeout=4000")
    return connection


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def overview() -> dict[str, Any]:
    with connect_catalog() as db:
        counts = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                  for name in ("fires", "exoplanets", "asteroids", "publications", "imagery", "fire_guidance")}
        fire_products = _rows(db, """SELECT source_product AS product,COUNT(*) AS observations,
          ROUND(AVG(frp_mw),3) AS mean_frp_mw,ROUND(SUM(frp_mw),3) AS sum_frp_mw,
          MIN(observed_at_utc) AS first_observation_utc,MAX(observed_at_utc) AS last_observation_utc
          FROM fires GROUP BY source_product ORDER BY source_product""")
        fire_days = _rows(db, """SELECT substr(observed_at_utc,1,10) AS day_utc,source_product AS product,
          COUNT(*) AS observations,ROUND(AVG(frp_mw),3) AS mean_frp_mw
          FROM fires WHERE observed_at_utc IS NOT NULL GROUP BY day_utc,source_product ORDER BY day_utc,source_product""")
        planet_years = _rows(db, """SELECT discovery_year AS year,COUNT(*) AS planets FROM exoplanets
          WHERE discovery_year IS NOT NULL GROUP BY discovery_year ORDER BY discovery_year""")
        planet_methods = _rows(db, """SELECT COALESCE(discovery_method,'Not reported') AS method,COUNT(*) AS planets
          FROM exoplanets GROUP BY discovery_method ORDER BY planets DESC,method LIMIT 12""")
        asteroid_classes = _rows(db, """SELECT COALESCE(orbit_class,'Not reported') AS orbit_class,COUNT(*) AS objects
          FROM asteroids GROUP BY orbit_class ORDER BY objects DESC,orbit_class LIMIT 20""")
        asteroid_status = _rows(db, """SELECT COALESCE(neo,'Not reported') AS neo,COALESCE(pha,'Not reported') AS pha,
          COUNT(*) AS objects FROM asteroids GROUP BY neo,pha ORDER BY objects DESC""")
        planet_points = _rows(db, """SELECT planet_name,host_name,discovery_year,planet_radius_earth,orbital_period_days
          FROM exoplanets WHERE planet_radius_earth IS NOT NULL AND orbital_period_days IS NOT NULL
          ORDER BY planet_name LIMIT 500""")
        asteroid_points = _rows(db, """SELECT full_name,orbit_class,neo,pha,semimajor_axis_au,eccentricity,period_days
          FROM asteroids WHERE semimajor_axis_au IS NOT NULL AND eccentricity IS NOT NULL
          ORDER BY spkid LIMIT 500""")
        images = _rows(db, """SELECT image_id,sensor,layer,date_utc,west,south,east,north,crs,filename,sha256,width_px,height_px,source_url
          FROM imagery ORDER BY date_utc,sensor""")
        meta = {row["key"]: row["value"] for row in db.execute("SELECT key,value FROM metadata")}
    return {"counts": counts, "fire_products": fire_products, "fire_days": fire_days,
            "exoplanets_by_year": planet_years, "exoplanet_methods": planet_methods,
            "asteroid_classes": asteroid_classes, "asteroid_neo_pha": asteroid_status,
            "planet_points": planet_points, "asteroid_points": asteroid_points,
            "images": images, "catalog_built_at_utc": meta.get("built_at_utc"),
            "sources": {"firms": "NASA FIRMS Area API", "exoplanets": "NASA Exoplanet Archive pscomppars",
                        "asteroids": "NASA/JPL SBDB Query API", "publications": "NASA NTRS",
                        "imagery": "NASA GIBS corrected-reflectance WMS"},
            "limitations": ["FIRMS points are thermal anomalies, not confirmed perimeters, causes, or severity.",
                            "Counts are one-day global product responses; product counts are sensor-specific and not directly interchangeable.",
                            "The full exoplanet export has 703 provider fields; this index exposes a typed analysis projection.",
                            "The 100,000 SBDB rows are the requested query limit, not the complete small-body population.",
                            "NTRS rows are citations/abstracts, not raw microgravity instrument data."]}


def query(dataset: str, *, q: str = "", product: str = "", confidence: str = "",
          date_from: str = "", date_to: str = "", bbox: str = "", year: int | None = None,
          orbit_class: str = "", neo: str = "", pha: str = "", limit: int = 50, offset: int = 0,
          sort: str = "") -> dict[str, Any]:
    limit = min(max(int(limit), 1), 100)
    offset = min(max(int(offset), 0), 100_000)
    q = q.strip()[:120]
    where: list[str] = []
    params: list[Any] = []
    if dataset == "fires":
        if product:
            if product not in PRODUCTS:
                raise HTTPException(status_code=422, detail="Unsupported satellite product.")
            where.append("source_product=?")
            params.append(product)
        if confidence:
            where.append("confidence=?")
            params.append(confidence[:40])
        for value, op in ((date_from, ">="), (date_to, "<=")):
            if value:
                if not DATE_RE.fullmatch(value):
                    raise HTTPException(status_code=422, detail="Dates must use YYYY-MM-DD.")
                where.append(f"substr(observed_at_utc,1,10){op}?")
                params.append(value)
        if bbox:
            try:
                west, south, east, north = [float(x) for x in bbox.split(",")]
                if not (-180 <= west <= 180 and -180 <= east <= 180 and -90 <= south <= 90 and -90 <= north <= 90 and west < east and south < north):
                    raise ValueError
            except ValueError:
                raise HTTPException(status_code=422, detail="Use a valid west,south,east,north bounding box.") from None
            where += ["longitude>=?", "longitude<=?", "latitude>=?", "latitude<=?"]
            params += [west, east, south, north]
        clause = " WHERE " + " AND ".join(where) if where else ""
        order = {"time_asc": "observed_at_utc ASC", "frp_desc": "frp_mw DESC", "time_desc": "observed_at_utc DESC"}.get(sort, "observed_at_utc DESC")
        select = "id,source_product,observed_at_utc,latitude,longitude,satellite,instrument,confidence,frp_mw,brightness_k,bright_ti4_k,bright_ti5_k,bright_t31_k,scan_km,track_km,daynight,product_version,source_file,source_sha256"
        table = "fires"
    elif dataset == "exoplanets":
        if year is not None:
            if not 1900 <= int(year) <= 2100:
                raise HTTPException(status_code=422, detail="Discovery year is outside the supported range.")
            where.append("discovery_year=?")
            params.append(int(year))
        if q:
            where.append("(instr(lower(planet_name),lower(?))>0 OR instr(lower(COALESCE(host_name,'')),lower(?))>0)")
            params += [q, q]
        clause = " WHERE " + " AND ".join(where) if where else ""
        order = {"year": "discovery_year DESC,planet_name", "radius": "planet_radius_earth DESC", "period": "orbital_period_days ASC"}.get(sort, "planet_name COLLATE NOCASE")
        select = "id,planet_name,host_name,discovery_year,discovery_method,discovery_facility,ra_deg,dec_deg,distance_pc,stellar_teff_k,stellar_mass_solar,stellar_radius_solar,planet_mass_earth,planet_mass_err1,planet_mass_err2,planet_radius_earth,planet_radius_err1,planet_radius_err2,orbital_period_days,orbital_period_err1,orbital_period_err2,semimajor_axis_au,semimajor_axis_err1,semimajor_axis_err2,eccentricity,insolation_earth,equilibrium_temp_k,source_ref,source_sha256"
        table = "exoplanets"
    elif dataset == "asteroids":
        if orbit_class:
            where.append("orbit_class=?")
            params.append(orbit_class[:30])
        if neo in {"Y", "N"}:
            where.append("neo=?")
            params.append(neo)
        if pha in {"Y", "N"}:
            where.append("pha=?")
            params.append(pha)
        if q:
            where.append("(instr(lower(COALESCE(full_name,'')),lower(?))>0 OR instr(lower(COALESCE(pdes,'')),lower(?))>0)")
            params += [q, q]
        clause = " WHERE " + " AND ".join(where) if where else ""
        order = {"moid": "moid_au ASC", "diameter": "diameter_km DESC", "epoch": "epoch_jd_tdb DESC"}.get(sort, "spkid ASC")
        select = "spkid,full_name,kind,pdes,orbit_class,neo,pha,moid_au,orbit_id,epoch_jd_tdb,eccentricity,semimajor_axis_au,perihelion_au,inclination_deg,ascending_node_deg,argument_perihelion_deg,mean_anomaly_deg,perihelion_time_jd,period_days,mean_motion_deg_day,aphelion_au,condition_code,first_obs,last_obs,observations_used,absolute_magnitude,diameter_km,albedo,source_file,source_sha256"
        table = "asteroids"
    elif dataset == "images":
        clause, order, table = "", "date_utc,sensor", "imagery"
        select = "image_id,sensor,layer,date_utc,west,south,east,north,crs,filename,sha256,width_px,height_px,source_url"
    elif dataset == "guidance":
        if q:
            where.append("(instr(lower(category),lower(?))>0 OR instr(lower(prevention),lower(?))>0)")
            params += [q, q]
        clause = " WHERE " + " AND ".join(where) if where else ""
        order, table = "category", "fire_guidance"
        select = "category,origin_note,prevention,scope_note,source_url"
    else:
        raise HTTPException(status_code=422, detail="Choose fires, exoplanets, asteroids, images, or guidance.")
    with connect_catalog() as db:
        total = db.execute(f"SELECT COUNT(*) FROM {table}{clause}", params).fetchone()[0]
        rows = _rows(db, f"SELECT {select} FROM {table}{clause} ORDER BY {order} LIMIT ? OFFSET ?", tuple(params + [limit, offset]))
    for row in rows:
        if dataset == "images":
            row["image_url"] = f"/science-images/{row['filename']}"
    return {"dataset": dataset, "items": rows, "total": total, "limit": limit,
            "offset": offset, "next_offset": offset + limit if offset + limit < total else None}


def ai_evidence(question: str) -> dict[str, Any]:
    text = question.casefold()
    if any(word in text for word in ("asteroid", "asteroids", "small body", "small-body", "كويكب", "الكويكبات", "جرم صغير")):
        dataset = "asteroids"
        result = query(dataset, q="", limit=8)
        with connect_catalog() as db:
            classes = _rows(db, "SELECT orbit_class,COUNT(*) AS count FROM asteroids GROUP BY orbit_class ORDER BY count DESC LIMIT 8")
            safety = _rows(db, "SELECT neo,pha,COUNT(*) AS count FROM asteroids GROUP BY neo,pha ORDER BY count DESC")
        return {"tool": "jpl_sbdb_catalog_query", "dataset": dataset, "total_records": result["total"], "records": result["items"], "classes": classes,
                "neo_pha_counts": safety, "source": "https://ssd-api.jpl.nasa.gov/doc/sbdb_query.html",
                "limitation": "The indexed subset is capped at the requested 100,000 JPL SBDB asteroid rows; an NEO/PHA flag is not a collision prediction."}
    if any(word in text for word in ("planet", "planets", "exoplanet", "exoplanets", "كوكب", "كواكب", "كوكب خارجي")):
        result = query("exoplanets", q="", limit=12, sort="year")
        with connect_catalog() as db:
            years = _rows(db, "SELECT discovery_year AS year,COUNT(*) AS planets FROM exoplanets GROUP BY discovery_year ORDER BY discovery_year")
        return {"tool": "exoplanet_archive_query", "dataset": "exoplanets", "total_records": result["total"], "records": result["items"],
                "discovery_counts_by_year": years, "source": "https://exoplanetarchive.ipac.caltech.edu/TAP/usingTAP.html",
                "limitation": "Catalogue values and their uncertainties are reported per provider; equilibrium temperature is not a direct surface-temperature measurement."}
    if any(word in text for word in ("fire", "fires", "firms", "wildfire", "hotspot", "frp", "viirs", "modis", "رصد", "حرائق", "حريق", "نار", "حراري")):
        with connect_catalog() as db:
            product = _rows(db, "SELECT source_product,COUNT(*) AS count,ROUND(AVG(frp_mw),3) AS mean_frp_mw,MIN(observed_at_utc) AS first_utc,MAX(observed_at_utc) AS last_utc FROM fires GROUP BY source_product ORDER BY source_product")
            examples = _rows(db, "SELECT source_product,observed_at_utc,latitude,longitude,confidence,frp_mw,satellite,instrument FROM fires ORDER BY observed_at_utc DESC LIMIT 8")
        return {"tool": "nasa_firms_multisensor_summary", "dataset": "fires", "product_counts": product,
                "example_observations": examples, "source": "https://firms.modaps.eosdis.nasa.gov/api/area/",
                "limitation": "A FIRMS pixel is a thermal anomaly; it cannot establish a confirmed fire, perimeter, ignition cause, or direct equivalence between sensor products."}
    with connect_catalog() as db:
        counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("fires", "exoplanets", "asteroids", "publications", "imagery", "fire_guidance")}
    return {"tool": "science_catalog_overview", "counts": counts,
            "source": "MORS normalized catalog; see per-dataset source metadata.",
            "limitation": "A catalog count describes the indexed records and does not imply completeness of the scientific population."}
