"""Bounded, read-only NASA FIRMS area observations."""
from __future__ import annotations

import csv
import io
import math
import re
import urllib.error
import urllib.request


SOURCES = {"MODIS_NRT", "MODIS_SP", "VIIRS_SNPP_NRT", "VIIRS_SNPP_SP",
           "VIIRS_NOAA20_NRT", "VIIRS_NOAA20_SP", "VIIRS_NOAA21_NRT", "VIIRS_NOAA21_SP"}
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
MAX_OBSERVATIONS = 250_000


class FirmsError(RuntimeError):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


def validate_bbox(raw: str) -> str:
    if raw.strip().lower() == "world":
        return "world"
    try:
        values = [float(value.strip()) for value in raw.split(",")]
    except ValueError as exc:
        raise ValueError("bbox must be west,south,east,north") from exc
    if len(values) != 4 or not all(math.isfinite(v) for v in values):
        raise ValueError("bbox must contain four finite coordinates")
    west, south, east, north = values
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("bbox coordinates are outside geographic bounds")
    if (east-west) * (north-south) > 100:
        raise ValueError("bbox area must be at most 100 square degrees")
    return ",".join(f"{value:g}" for value in values)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def fetch_area_with_raw(map_key: str, source: str, bbox: str, days: int) -> tuple[list[dict], bytes]:
    if not re.fullmatch(r"[A-Za-z0-9]{16,64}", map_key):
        raise FirmsError("credential", "FIRMS MAP_KEY format is invalid")
    if source not in SOURCES or not 1 <= days <= 5:
        raise ValueError("Unsupported FIRMS source or day range")
    coordinates = validate_bbox(bbox)
    # The key is placed only in NASA's required path and never returned or logged.
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{source}/{coordinates}/{days}"
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers={"User-Agent": "MORS-AEGIS/0.2"}), timeout=15) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise FirmsError("credential", "FIRMS rejected the MAP_KEY") from None
        if exc.code == 429:
            raise FirmsError("rate_limit", "FIRMS rate limit reached") from None
        raise FirmsError("upstream", f"FIRMS returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise FirmsError("network", "FIRMS connection failed or timed out") from None
    if len(content) > MAX_RESPONSE_BYTES:
        raise FirmsError("response_limit", "FIRMS response exceeded the local size limit")
    try:
        text = content.decode("utf-8-sig")
        if "map key" in text[:500].lower() or "invalid key" in text[:500].lower():
            raise FirmsError("credential", "FIRMS rejected the MAP_KEY")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if not reader.fieldnames or not {"latitude", "longitude", "acq_date", "acq_time"}.issubset(reader.fieldnames):
            raise FirmsError("format", "FIRMS response was not an observation CSV")
        rows = []
        for row in reader:
            if len(rows) >= MAX_OBSERVATIONS:
                raise FirmsError("response_limit", "FIRMS returned too many observations for this request")
            rows.append({"source_product": source, "latitude": float(row["latitude"]),
                         "longitude": float(row["longitude"]), "acq_date": row["acq_date"],
                         "acq_time": row["acq_time"], "satellite": row.get("satellite"),
                         "instrument": row.get("instrument"), "confidence": row.get("confidence"),
                         "frp": float(row["frp"]) if row.get("frp") else None,
                         "version": row.get("version"), "original": row})
        return rows, content
    except (UnicodeError, csv.Error, TypeError, ValueError, KeyError):
        raise FirmsError("format", "FIRMS observation CSV could not be parsed") from None


def fetch_area(map_key: str, source: str, bbox: str, days: int) -> list[dict]:
    """Compatibility wrapper for callers that only need parsed observations."""
    rows, _ = fetch_area_with_raw(map_key, source, bbox, days)
    return rows
