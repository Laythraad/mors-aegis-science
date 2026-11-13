import hashlib
import io
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setenv("AEGIS_ACCESS_TOKEN", "test-only-secret-0123456789abcdef")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test-aegis.db")
    with TestClient(app) as test_client:
        test_client.headers.update({"Authorization": "Bearer test-only-secret-0123456789abcdef"})
        yield test_client


def test_health_and_mission_truthfully_report_catalog(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["database"] == "connected"
    mission = client.get("/api/mission").json()
    assert mission["counts"]["verified_experiment_records"] == 3
    assert mission["counts"]["raw_flight_datasets_ingested"] == 0
    assert mission["earth_fire"]["hotspots"] is None


def test_session_is_random_and_logout_revokes_stolen_cookie(client):
    secret = 'test-only-secret-0123456789abcdef'
    client.headers.pop('Authorization')
    login = client.post('/api/session', json={'token': secret})
    assert login.status_code == 200
    cookie = client.cookies.get('aegis_session')
    assert cookie and cookie != secret
    assert 'HttpOnly' in login.headers['set-cookie'] and 'SameSite=strict' in login.headers['set-cookie']
    assert client.get('/api/mission').status_code == 200
    assert client.delete('/api/session').status_code == 200
    assert client.get('/api/mission', headers={'Cookie': 'aegis_session=' + cookie}).status_code == 401
    assert client.get('/api/mission', headers={'Cookie': 'aegis_session=' + secret}).status_code == 401


def test_session_expiry_and_capacity(monkeypatch):
    from app import security
    security._sessions.clear()
    clock = [100.0]
    monkeypatch.setattr(security.time, 'monotonic', lambda: clock[0])
    token = security.issue_session('local')
    assert security.session_owner(token) == 'local'
    clock[0] += security._SESSION_TTL
    assert security.session_owner(token) is None
    for _ in range(1025):
        security.issue_session('local')
    assert len(security._sessions) == 1024
    security._sessions.clear()


def test_https_proxy_can_require_secure_cookie(client, monkeypatch):
    monkeypatch.setenv('AEGIS_COOKIE_SECURE', '1')
    response = client.post('/api/session', json={'token': 'test-only-secret-0123456789abcdef'})
    assert response.status_code == 200
    assert '; secure' in response.headers['set-cookie'].lower()


def test_ollama_health_does_not_confuse_different_model_tags(client, monkeypatch):
    import app.main as main
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen2.5:3b')
    monkeypatch.setattr(main, 'read_json', lambda *args, **kwargs: {'models': [{'name': 'qwen2.5:7b'}]})
    assert client.get('/api/integrations/check/ollama').json()['status'] == 'model_missing'
    monkeypatch.setattr(main, 'read_json', lambda *args, **kwargs: {'models': [{'name': 'qwen2.5:3b'}]})
    assert client.get('/api/integrations/check/ollama').json()['status'] == 'live'
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen2.5')
    monkeypatch.setattr(main, 'read_json', lambda *args, **kwargs: {'models': [{'name': 'qwen2.5:latest'}]})
    assert client.get('/api/integrations/check/ollama').json()['status'] == 'live'


def test_experiment_search_includes_original_nasa_source(client):
    result = client.get("/api/experiments", params={"q": "smoldering"})
    assert result.status_code == 200
    record = result.json()["items"][0]
    assert record["source_id"] == "19970020606"
    assert record["record"].startswith("https://ntrs.nasa.gov/citations/")
    assert record["evidence_type"] == "NASA NTRS record and abstract"


def test_incompatible_records_do_not_produce_numeric_conclusion(client):
    result = client.post("/api/compare", json={"experiment_ids": ["NASA-NTRS-19970020606", "NASA-NTRS-20210015913"]})
    assert result.status_code == 200
    assert result.json()["same_metadata_categories"] is False
    assert "cannot be established" in result.json()["conclusion"]


def test_rgb_heuristic_returns_overlay_and_never_temperature(client):
    image = Image.new("RGB", (4, 4), (0, 0, 0))
    image.putpixel((1, 2), (255, 210, 40))
    data = io.BytesIO()
    image.save(data, format="PNG")
    result = client.post("/api/vision/analyze", files={"file": ("sample.png", data.getvalue(), "image/png")})
    assert result.status_code == 200
    body = result.json()
    assert body["warm_pixel_count"] == 1
    assert body["bounding_box_px"] == {"x_min_px": 1, "x_max_px": 1, "y_min_px": 2, "y_max_px": 2}
    assert body["thermal_measurement"] is None
    assert body["source_experiment"] is None
    assert body["overlay_png_base64"]


def test_vision_threshold_sensitivity_is_reproducible_and_bounded(client):
    image = Image.new("RGB", (3, 1), (0, 0, 0))
    image.putpixel((0, 0), (160, 100, 10))
    image.putpixel((1, 0), (210, 100, 10))
    raw = io.BytesIO()
    image.save(raw, format="PNG")
    content = raw.getvalue()
    def run(threshold):
        return client.post(f"/api/vision/analyze?red_min={threshold}",
                           files={"file": ("sample.png", content, "image/png")})
    low = run(150).json()
    high = run(200).json()
    assert low["warm_pixel_count"] == 2
    assert high["warm_pixel_count"] == 1
    assert low["source_sha256"] == high["source_sha256"] == hashlib.sha256(content).hexdigest()
    assert low["parameters"]["red_min_exclusive"] == 150
    counts = [item["warm_pixel_count"] for item in low["threshold_sensitivity"]]
    assert counts == sorted(counts, reverse=True)
    assert run(256).status_code == 422


def test_bass_ii_source_table_is_traceable_and_preserves_values(client):
    response = client.get("/api/combustion/bass-ii")
    assert response.status_code == 200
    data = response.json()
    assert data["source_url"].endswith("/PSI-25")
    assert len(data["rows"]) == 129
    assert data["rows"][0]["Test #"] == "B1"
    assert data["rows"][0]["Calibrated  initial O2 % by vol "] == "22.2"
    assert data["doi"] == "https://doi.org/10.60555/4qc4-de67"
    assert data["license"] == "CC0-1.0"


def test_bass_overview_counts_and_provenance_are_derived_from_source(client):
    source = client.get("/api/combustion/bass-ii").json()
    overview = client.get("/api/combustion/bass-ii/overview", params={"measure": "carbon_dioxide"}).json()
    assert overview["total"] == 129
    assert overview["initial_count"] == 127
    assert overview["final_count"] == 123
    assert overview["paired_count"] == len(overview["pairs"])
    assert overview["source_sha256"] == source["sha256"]
    for pair in overview["pairs"]:
        row = source["rows"][pair["row_index"]]
        assert pair["test"] == row["Test #"]
        assert pair["initial"] == float(row["Initial CO2 % by vol"])
        assert pair["final"] == float(row["Final CO2 % by vol"])
    assert client.get("/api/combustion/bass-ii/overview?measure=invalid").status_code == 422


def test_nasa_bass_representative_image_is_available_for_exploratory_analysis(client):
    image = client.get("/bass-ii-nasa-representative.jpg")
    assert image.status_code == 200
    assert hashlib.sha256(image.content).hexdigest() == "aa0bf2369cf77833e95e353519e634ab5cbb5b2918db08849e9bde82267aade3"
    response = client.post("/api/vision/analyze", files={"file": ("nasa-bass.jpg", image.content, "image/jpeg")})
    assert response.status_code == 200
    assert response.json()["thermal_measurement"] is None
    assert response.json()["warm_pixel_count"] > 0


@pytest.mark.parametrize(("mode", "total", "pairs"), [("normal", 207, 127), ("inverse", 120, 109)])
def test_flame_design_retains_recorded_values_and_configuration(client, mode, total, pairs):
    result = client.get("/api/combustion/flame-design", params={"configuration": mode})
    assert result.status_code == 200
    data = result.json()
    assert data["configuration"] == mode
    assert (data["records"], data["paired_count"]) == (total, pairs)
    assert data["doi"] == "https://doi.org/10.60555/w4zy-bt45"
    raw = client.get("/" + data["source_filename"]).content
    assert hashlib.sha256(raw).hexdigest() == data["source_sha256"]
    for pair in data["pairs"]:
        assert pair["pressure_atm"] == float(pair["source_row"]["pmean (atm)"])
        assert pair["flow_mg_s"] == float(pair["source_row"]["mtot (mg/s)"])


def test_flame_design_rejects_unknown_and_altered_source(client, monkeypatch, tmp_path):
    from app import flame_design
    assert client.get("/api/combustion/flame-design?configuration=unknown").status_code == 422
    (tmp_path / "psi-10-normal.csv").write_text("altered", encoding="utf-8")
    monkeypatch.setattr(flame_design, "ROOT", tmp_path)
    assert client.get("/api/combustion/flame-design?configuration=normal").status_code == 503


def test_flame_design_search_keeps_original_row_and_assistant_selection(client, monkeypatch):
    response = client.get("/api/combustion/flame-design/records", params={"configuration": "normal", "q": "19115A1"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["row_index"] == 0
    assert data["items"][0]["source_row"]["Test"] == "19115A1"
    page = client.get("/api/combustion/flame-design/records", params={"configuration": "normal", "limit": 1, "offset": 1}).json()
    assert page["items"][0]["row_index"] == 1
    monkeypatch.setenv("OLLAMA_MODEL", "invalid model name")
    answer = client.post("/api/ai/chat", json={"message": "Explain the selected ACME test",
                         "flame_selection": {"configuration": "normal", "row_index": 0}})
    assert answer.status_code == 200
    assert answer.json()["tool_result"]["items"][0]["source_row"] == data["items"][0]["source_row"]
    assert "19115A1" in answer.json()["answer"]
    missing = client.post("/api/ai/chat", json={"message": "Explain the selected ACME test",
                          "flame_selection": {"configuration": "normal", "row_index": 999}})
    assert missing.status_code == 422


def test_combustion_inventory_reports_each_verified_source(client, monkeypatch, tmp_path):
    from app import flame_design
    sources = client.get("/api/combustion/sources").json()["sources"]
    assert [(source["id"], source["records"]) for source in sources] == [
        ("bass_ii", 129), ("flame_normal", 207), ("flame_inverse", 120),
        ("cool_normal", 179), ("cool_inverse", 154)]
    assert all(source["status"] == "verified" for source in sources)
    monkeypatch.setattr(flame_design, "ROOT", tmp_path)
    sources = client.get("/api/combustion/sources").json()["sources"]
    assert sources[0]["status"] == "verified"
    assert sources[1]["status"] == sources[2]["status"] == "unavailable"
    assert sources[3]["status"] == sources[4]["status"] == "verified"
    assert sources[4]["source_rows"] == 1015
    assert sources[4]["blank_rows"] == 861


def test_combustion_index_search_pagination_and_source_integrity(client, monkeypatch, tmp_path):
    from app import cool_flames
    result = client.get("/api/combustion/index").json()
    assert result["total"] == 789
    assert len(result["items"]) == 25
    found = client.get("/api/combustion/index", params={"dataset": "flame_normal", "q": "19115A1"}).json()
    assert found["total"] == 1
    assert found["items"][0]["source_row"]["Test"] == "19115A1"
    assert found["items"][0]["row_index"] == 0
    assert client.get("/api/combustion/index", params={"q": "%"}).json()["total"] < 789
    page = client.get("/api/combustion/index", params={"dataset": "bass_ii", "limit": 1, "offset": 1}).json()
    assert page["total"] == 129 and page["items"][0]["row_index"] == 1
    assert client.get("/api/combustion/index?dataset=bogus").status_code == 422
    monkeypatch.setattr(cool_flames, "ROOT", tmp_path)
    assert client.get("/api/combustion/index").status_code == 503


def test_combustion_index_concurrent_initialization_is_consistent(client):
    def query(_):
        return client.get("/api/combustion/index?limit=1")
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(query, range(4)))
    assert all(response.status_code == 200 and response.json()["total"] == 789 for response in responses)


def test_cool_flame_duration_distribution_uses_all_valid_durations(client):
    from app.bass import finite_number
    from statistics import median
    for mode in ("normal", "inverse"):
        data = client.get("/api/combustion/cool-flames", params={"configuration": mode}).json()
        raw = [(row["row_index"], finite_number(row["source_row"].get("burn time (sec)")))
               for row in data["selected_source_rows"]]
        values = [(index, value) for index, value in raw if value is not None]
        distribution = data["duration_distribution"]
        assert distribution["count"] == len(values)
        assert distribution["missing_or_nonnumeric"] == len(raw) - len(values)
        assert distribution["median_s"] == median(value for _, value in values)
        assert distribution["count"] > data["paired_count"]
        seen = []
        lookup = dict(values)
        for bin_ in distribution["bins"]:
            assert bin_["count"] == len(bin_["row_indices"])
            for index in bin_["row_indices"]:
                value = lookup[index]
                assert bin_["lower_s"] <= value
                assert value <= bin_["upper_s"] if bin_["upper_inclusive"] else value < bin_["upper_s"]
                seen.append(index)
        assert sorted(seen) == sorted(lookup)


def test_cool_duration_empty_and_constant_values():
    from app.cool_flames import duration_distribution
    assert duration_distribution([(3, {"burn time (sec)": "missing"})])["bins"] == []
    result = duration_distribution([(2, {"burn time (sec)": "0"}), (9, {"burn time (sec)": "0"})])
    assert result["median_s"] == 0
    assert result["bins"] == [{"lower_s": 0, "upper_s": 0, "upper_inclusive": True,
                               "row_indices": [2, 9], "count": 2}]


def test_assistant_uses_exact_cfi_selection_and_verified_summary(client, monkeypatch, tmp_path):
    from app import cool_flames
    monkeypatch.setenv("OLLAMA_MODEL", "invalid model name")
    selection = {"configuration": "normal", "fuel": "30% butane"}
    response = client.post("/api/ai/chat", json={"message": "اشرح هذه البيانات", "cool_selection": selection})
    assert response.status_code == 200
    data = response.json()
    assert data["model"] is None
    result = data["tool_result"]
    assert result["tool"] == "cool_flames_selected_summary"
    assert result["configuration"] == selection["configuration"] and result["fuel"] == selection["fuel"]
    assert result["selected_records"] == 52 and result["duration_distribution"]["count"] == 52
    assert result["paired_count"] == 34
    assert result["records"][0]["url"] == cool_flames.DOI
    assert {item["id"] for item in result["background_references"]} == {"20210015913", "20220015583", "20250001364"}
    assert "حرارة الموقد ليست حرارة اللهب" in data["answer"]
    bad = client.post("/api/ai/chat", json={"message": "Explain", "cool_selection": {"configuration": "normal", "fuel": "not a fuel"}})
    assert bad.status_code == 422
    ambiguous = client.post("/api/ai/chat", json={"message": "Explain", "cool_selection": selection, "bass_selection": [0, 1]})
    assert ambiguous.status_code == 422
    monkeypatch.setattr(cool_flames, "ROOT", tmp_path)
    missing = client.post("/api/ai/chat", json={"message": "Explain", "cool_selection": selection})
    assert missing.status_code == 503


def test_curated_nasa_references_are_scoped_and_linked(client):
    all_items = client.get("/api/combustion/references").json()["items"]
    assert len(all_items) == 4
    assert all(item["url"] == "https://ntrs.nasa.gov/citations/" + item["id"] for item in all_items)
    assert all(item["scope_ar"] and item["limit_ar"] and item["document_type"] for item in all_items)
    bass = client.get("/api/combustion/references?topic=bass_ii").json()["items"]
    assert [item["id"] for item in bass] == ["20210011385"]
    acme = client.get("/api/combustion/references?topic=cool_flames").json()["items"]
    assert len(acme) == 3
    assert client.get("/api/combustion/references?topic=unrelated").status_code == 422


def test_flex_source_filter_and_reproducible_statistics(client, monkeypatch, tmp_path):
    from app import flex
    result = client.get('/api/combustion/flex').json()
    assert result['total_rows'] == 274
    assert result['selected_count'] == 274
    assert result['valid_rate_count'] == 258
    assert result['missing_rate_count'] == 16
    assert result == client.get('/api/combustion/flex').json()
    selected = client.get('/api/combustion/flex?fuel=Methanol&pressure=normal').json()
    assert selected['selected_count'] > 0
    assert all(row['fuel'] == 'Methanol' and row['pressure_band'] == 'normal' for row in selected['rows'])
    values = [row['rate_mm2_s'] for row in selected['rows'] if row['rate_mm2_s'] is not None]
    assert abs(selected['mean_rate_mm2_s'] - sum(values) / len(values)) < 1e-12
    assert client.get('/api/combustion/flex?fuel=invalid').status_code == 422
    monkeypatch.setattr(flex, 'ROOT', tmp_path)
    assert client.get('/api/combustion/flex').status_code == 503


@pytest.mark.parametrize(("mode", "total", "pairs", "temp_field"),
                         [("normal", 179, 133, "Peak burner T (C )"),
                          ("inverse", 1015, 151, "Peak burner Temp (C)")])
def test_cool_flame_tables_preserve_source_pairs(client, mode, total, pairs, temp_field):
    response = client.get("/api/combustion/cool-flames", params={"configuration": mode})
    assert response.status_code == 200
    data = response.json()
    assert (data["records"], data["paired_count"]) == (total, pairs)
    assert data["doi"] == "https://doi.org/10.60555/cyt1-kh64"
    raw = client.get("/" + data["source_filename"]).content
    assert hashlib.sha256(raw).hexdigest() == data["source_sha256"]
    for item in data["pairs"]:
        assert item["burn_time_s"] == float(item["source_row"]["burn time (sec)"])
        assert item["peak_burner_c"] == float(item["source_row"][temp_field])
    assert client.get("/api/combustion/cool-flames?configuration=invalid").status_code == 422


def test_cool_flame_rejects_corrupted_source(client, monkeypatch, tmp_path):
    from app import cool_flames
    (tmp_path / "psi-159-normal.csv").write_text("altered", encoding="utf-8")
    monkeypatch.setattr(cool_flames, "ROOT", tmp_path)
    assert client.get("/api/combustion/cool-flames?configuration=normal").status_code == 503


def test_cool_flame_fuel_filter_and_blank_rows_preserve_source_counts(client):
    all_rows = client.get("/api/combustion/cool-flames?configuration=inverse").json()
    assert (all_rows["records"], all_rows["nonempty_records"], all_rows["blank_rows"]) == (1015, 154, 861)
    assert sum(entry["count"] for entry in all_rows["hot_ignition_categories"]) == 154
    assert {entry["source_value"] for entry in all_rows["hot_ignition_categories"]} >= {"Yes", "yes", "No", "no", "flash"}
    filtered = client.get("/api/combustion/cool-flames", params={"configuration": "inverse", "fuel": "ethane"}).json()
    assert filtered["selected_records"] == 53
    assert all(row["fuel"] == "ethane" for row in filtered["pairs"])
    assert sum(entry["count"] for entry in filtered["hot_ignition_categories"]) == 53
    assert client.get("/api/combustion/cool-flames?configuration=inverse&fuel=invalid").status_code == 422


def test_cool_flame_replay_detects_changed_source_or_analysis(client):
    import json
    data = client.get("/api/combustion/cool-flames", params={"configuration": "inverse", "fuel": "ethane"}).json()
    saved_hash = data.pop("analysis_sha256")
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == saved_hash
    assert len(data["selected_source_rows"]) == 53
    payload = {"configuration": "inverse", "fuel": "ethane", "source_sha256": data["source_sha256"],
               "analysis_sha256": saved_hash, "method_version": data["reproducibility"]["method_version"]}
    replay = client.post("/api/combustion/cool-flames/replay", json=payload)
    assert replay.status_code == 200 and replay.json()["matched"] is True
    changed = client.post("/api/combustion/cool-flames/replay", json=payload | {"analysis_sha256": "0"*64}).json()
    assert changed["matched"] is False and changed["checks"]["analysis_sha256"] is False
    changed = client.post("/api/combustion/cool-flames/replay", json=payload | {"source_sha256": "0"*64}).json()
    assert changed["matched"] is False and changed["checks"]["source_sha256"] is False
    changed = client.post("/api/combustion/cool-flames/replay", json=payload | {"method_version": "different"}).json()
    assert changed["matched"] is False and changed["checks"]["method_version"] is False


def test_bass_comparison_preserves_missing_values_and_reproduces_results(client, monkeypatch):
    payload = {"first_index": 0, "second_index": 1}
    response = client.post("/api/combustion/bass-ii/compare", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["tests"][0]["test"] == "B1"
    assert result["tests"][0]["measurements"]["oxygen"]["change"] == 0
    assert result["tests"][1]["measurements"]["oxygen"]["change"] == -20.6
    assert result["tests"][1]["measurements"]["carbon_dioxide"]["final"] is None
    assert result["tests"][1]["measurements"]["carbon_dioxide"]["change"] is None
    checks = {item["criterion"]: item for item in result["condition_checks"]}
    assert checks["sample_description"]["outcome"] == "different_source_text"
    assert checks["initial_oxygen"]["outcome"] == "same_recorded_value"
    assert result["comparability"] == "unverified"
    assert result["condition_status"] == "recorded_differences"
    assert "sample_description" in result["different_recorded_criteria"]
    assert "not physical equivalence" in result["condition_check_note"]
    assert result == client.post("/api/combustion/bass-ii/compare", json=payload).json()
    assert client.post("/api/combustion/bass-ii/compare", json={"first_index": 0, "second_index": 0}).status_code == 422
    assert client.post("/api/combustion/bass-ii/compare", json={"first_index": 0, "second_index": 999}).status_code == 422
    monkeypatch.setenv("OLLAMA_MODEL", "invalid model name")
    answer = client.post("/api/ai/chat", json={"message": "Explain these records", "bass_selection": [0, 1]})
    assert answer.status_code == 200
    assert answer.json()["tool_result"]["tests"] == result["tests"]
    assert "B1" in answer.json()["answer"] and "B2" in answer.json()["answer"]


def test_bass_condition_checks_do_not_treat_missing_as_match(monkeypatch):
    from app import bass
    table = bass.experimental_table()
    table["rows"][0]["Fan display"] = " "
    table["rows"][1]["Fan display"] = "none"
    table["rows"][0]["Calibrated  initial O2 % by vol "] = "NaN"
    monkeypatch.setattr(bass, "experimental_table", lambda: table)
    data = bass.compare_tests(0, 1)
    outcomes = {item["criterion"]: item["outcome"] for item in data["condition_checks"]}
    assert outcomes["fan_display"] == "unavailable"
    assert outcomes["initial_oxygen"] == "unavailable"


def test_bass_comparison_status_never_claims_physical_equivalence(monkeypatch):
    from app import bass
    table = bass.experimental_table()
    # Control every checked field to exercise each status without inferring physics.
    fields = ["Fuel Sample Material", "Flow restrictor", "Fan display", "Air display",
              "Calibrated  initial O2 % by vol "]
    for row in table["rows"][:2]:
        for field in fields:
            row[field] = "20.5" if field.startswith("Calibrated") else "same label"
    monkeypatch.setattr(bass, "experimental_table", lambda: table)
    matched = bass.compare_tests(0, 1)
    assert matched["condition_status"] == "no_recorded_differences"
    assert matched["comparability"] == "unverified"
    table["rows"][1]["Fan display"] = ""
    missing = bass.compare_tests(0, 1)
    assert missing["condition_status"] == "incomplete_metadata"
    assert missing["unavailable_criteria"] == ["fan_display"]
    table["rows"][1]["Fuel Sample Material"] = "different label"
    different = bass.compare_tests(0, 1)
    assert different["condition_status"] == "recorded_differences"
    assert different["different_recorded_criteria"] == ["sample_description"]
    assert different["unavailable_criteria"] == ["fan_display"]
    assert different["comparability"] == "unverified"


def test_timeseries_pipeline_calculates_metrics_and_persists_traceable_result(client, tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path / "uploads")
    raw = ("timestamp,value,unit,experiment_id,sensor,source\n"
           "2025-01-01T00:00:00Z,1.0,m/s,EXP-1,S-1,local-lab\n"
           "2025-01-01T00:01:00Z,2.0,m/s,EXP-1,S-1,local-lab\n"
           "2025-01-01T00:02:00Z,100.0,m/s,EXP-1,S-1,local-lab\n"
           "2025-01-01T00:03:00Z,4.0,m/s,EXP-1,S-1,local-lab\n").encode()
    response = client.post("/api/datasets/timeseries/analyze", files={"file": ("observations.csv", raw, "text/csv")})
    assert response.status_code == 200
    record = response.json()
    result = record["result"]
    assert record["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["n_rows"] == 4 and result["unit"] == "m/s"
    assert result["statistics"]["mean"] == 26.75
    assert [point["elapsed_seconds"] for point in result["time_series"]] == [0, 60, 120, 180]
    assert result["validation"]["deterministic_verification"]["status"] == "passed"
    assert result["validation"]["deterministic_verification"]["checks"]["mean_recomputed_with_fmean"] is True
    assert len(result["anomalies"]) == 1
    replay = client.post("/api/datasets/timeseries/analyze", files={"file": ("observations.csv", raw, "text/csv")})
    assert replay.json()["idempotent_replay"] is True
    assert client.get("/api/datasets/timeseries").json()["total"] == 1
    assert client.get(f"/api/datasets/timeseries/{record['sha256']}/export").status_code == 200


def test_csv_schema_units_nonfinite_and_ragged_rows_are_rejected(client):
    cases = [
        ("date,value\n2025-01-01,2", "Unsupported CSV columns"),
        ("timestamp,value,unit\n2025-01-01T00:00:00Z,1,K\n2025-01-01T00:01:00Z,2,C\n2025-01-01T00:02:00Z,3,K", "Mixed units"),
        ("timestamp,value\n2025-01-01T00:00:00Z,1\n2025-01-01T00:01:00Z,nan\n2025-01-01T00:02:00Z,3", "finite"),
        ("timestamp,value,unit\n2025-01-01T00:00:00Z,1,K\n2025-01-01T00:01:00Z,2,K,extra\n2025-01-01T00:02:00Z,3,K", "fields does not match"),
    ]
    for index, (body, expected) in enumerate(cases):
        response = client.post("/api/datasets/timeseries/analyze", files={"file": (f"bad{index}.csv", body.encode(), "text/csv")})
        assert response.status_code == 422
        assert expected in response.json()["detail"]


def test_quantum_api_runs_seeded_aer_circuit_and_persists_provenance(client):
    payload = {"n_qubits": 2, "shots": 1024, "seed": 9,
               "gates": [{"gate":"h","qubit":0}, {"gate":"cx","control":0,"target":1}]}
    response = client.post("/api/quantum/circuits/run", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["backend"]["name"].startswith("Qiskit AerSimulator")
    assert result["backend"]["hardware_execution"] is False
    assert set(result["counts"]).issubset({"00", "11"})
    assert result["validation"]["counts_match_shots"] is True
    assert result["state"]["is_entangled_across_qubit0_partition"] is True
    assert client.get("/api/quantum/experiments").json()["total"] == 1
    assert client.get(f"/api/quantum/experiments/{result['experiment_id']}").json()["experiment_id"] == result["experiment_id"]


def test_quantum_api_rejects_invalid_and_oversized_circuit(client):
    bad = client.post("/api/quantum/circuits/run", json={"n_qubits":2,"shots":128,"seed":1,"gates":[{"gate":"cx","control":0,"target":0}]})
    assert bad.status_code == 422
    large = client.post("/api/quantum/circuits/run", json={"n_qubits":9,"shots":128,"seed":1,"gates":[]})
    assert large.status_code == 422


def test_quantum_kernel_benchmark_compares_classical_baseline_without_advantage_claim(client):
    payload={"seed":41,"samples":[[-1,-.8],[-.7,-1.2],[.8,1],[1.2,.7],[-1.1,-.5],[.5,1.3],[.9,.5],[-.4,-.9]],"labels":[0,0,1,1,0,1,1,0]}
    response=client.post("/api/quantum/benchmarks/kernel",json=payload)
    assert response.status_code == 200
    result=response.json()
    assert len(result["quantum_simulation"]["kernel_matrix"]) == 8
    assert result["comparison"]["quantum_superiority_claimed"] is False
    assert result["classical_baseline"]["kernel"].startswith("standardized RBF")


def test_quantum_status_reports_no_hardware_and_frontend_has_lab_and_themes(client):
    status=client.get("/api/quantum/status").json()
    assert status["hardware"]["execution_enabled"] is False
    page=client.get("/").text
    assert 'data-view="quantum"' in page
    assert 'id="theme-select"' in page
    assert client.get("/mors-logo.svg").status_code == 200


def test_earth_data_is_not_invented_without_firms_key(client):
    result=client.get("/api/earth-fire").json()
    assert result["observations"] is None
    assert result["availability"] == "requires_key"
    assert "not a proxy for spacecraft combustion" in result["terrestrial_fire_note"]


def test_digital_twin_has_no_unvalidated_prediction(client):
    response=client.post("/api/digital-twin/explore",json={"oxygen_percent":21,"chamber_pressure_kpa":101,"flow_velocity_m_s":0.2})
    assert response.status_code == 200
    assert response.json()["outputs"] is None
    assert response.json()["classification"] == "HYPOTHESES"


def test_frontend_and_architecture_endpoints(client):
    page=client.get("/")
    assert page.status_code == 200
    assert "MORS AEGIS" in page.text
    architecture=client.get("/api/architecture").json()
    assert "Orchestrator Agent" in architecture["agents"]
    assert "Generative RAG/vector search" in architecture["not_implemented"]


def test_auth_headers_docs_and_login(client):
    assert client.get("/api/mission", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/api/mission").headers["x-content-type-options"] == "nosniff"
    assert client.post("/api/session", json={"token": "wrong"}).status_code == 401
    response = client.post("/api/session", json={"token": "test-only-secret-0123456789abcdef"})
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()


def test_owner_isolation_and_duplicate_compare(client, tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setenv("AEGIS_USERS_JSON", '{"second":"second-secret-0123456789abcdef"}')
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path / "uploads")
    raw = ("timestamp,value\n2025-01-01T00:00:00Z,1\n2025-01-01T00:01:00Z,2\n"
           "2025-01-01T00:02:00Z,3\n").encode()
    first = client.post("/api/datasets/timeseries/analyze", files={"file": ("x.csv", raw, "text/csv")}).json()
    second_headers = {"Authorization": "Bearer second-secret-0123456789abcdef"}
    assert client.get("/api/datasets/timeseries", headers=second_headers).json()["total"] == 0
    assert client.get(f"/api/datasets/timeseries/{first['sha256']}/result", headers=second_headers).status_code == 404
    second = client.post("/api/datasets/timeseries/analyze", files={"file": ("x.csv", raw, "text/csv")}, headers=second_headers)
    assert second.status_code == 200
    assert second.json()["dataset_id"] != first["dataset_id"]
    q = client.post("/api/quantum/circuits/run", json={"n_qubits": 1, "shots": 128, "seed": 1, "gates": []}).json()
    assert client.get(f"/api/quantum/experiments/{q['experiment_id']}", headers=second_headers).status_code == 404
    duplicate = client.post("/api/compare", json={"experiment_ids": ["NASA-NTRS-19970020606"] * 2})
    assert duplicate.status_code == 422


def test_rejects_oversized_image_dimensions_and_csv_fields(client):
    # PNG headers with huge dimensions must be rejected before pixel conversion.
    image = Image.new("RGB", (4000, 4001), (0, 0, 0))
    data = io.BytesIO()
    image.save(data, format="PNG")
    response = client.post("/api/vision/analyze", files={"file": ("large.png", data.getvalue(), "image/png")})
    assert response.status_code == 413
    body = ("timestamp,value,source\n" + "\n".join(
        f"2025-01-01T00:0{i}:00Z,{i},{'x'*513}" for i in range(3))).encode()
    response = client.post("/api/datasets/timeseries/analyze", files={"file": ("x.csv", body, "text/csv")})
    assert response.status_code == 422


def test_quantum_rejects_coerced_numbers(client):
    for value in (True, 1.5, "2"):
        result = client.post("/api/quantum/circuits/run", json={"n_qubits": value, "shots": 128, "gates": []})
        assert result.status_code == 422
    bad_kernel = client.post("/api/quantum/benchmarks/kernel", json={"samples": [1, 2, 3, 4], "labels": [0, 1, 0, 1]})
    assert bad_kernel.status_code == 422


def test_firms_live_rows_preserve_source_and_reject_oversized_regions(client, monkeypatch):
    import app.firms as firms
    monkeypatch.setenv("NASA_FIRMS_MAP_KEY", "testmapkey0123456789abcdef012345")
    csv_bytes = ("latitude,longitude,acq_date,acq_time,satellite,instrument,confidence,frp,version\n"
                 "33.5,-118.5,2026-11-05,1230,N,VIIRS,n,4.2,2.0NRT\n").encode()
    class Opener:
        def open(self, request, timeout):
            assert "firms.modaps.eosdis.nasa.gov" in request.full_url
            return io.BytesIO(csv_bytes)
    monkeypatch.setattr(firms.urllib.request, "build_opener", lambda *_: Opener())
    response = client.get("/api/earth-fire", params={"bbox": "-119,33,-118,34", "source": "VIIRS_SNPP_NRT", "days": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["availability"] == "live"
    assert body["observations"][0]["original"]["version"] == "2.0NRT"
    assert body["observations"][0]["source_product"] == "VIIRS_SNPP_NRT"
    params = {"start_date": "2026-11-05", "end_date": "2026-11-05",
              "bbox": "-119,33,-118,34", "product": "VIIRS_SNPP_NRT", "limit": 500}
    archived = client.get("/api/data/fire-observations", params=params)
    assert archived.status_code == 200
    assert archived.json()["total"] == 1
    assert archived.json()["items"][0]["observed_at_utc"].startswith("2026-11-05")
    assert archived.json()["items"][0]["product"] == "VIIRS_SNPP_NRT"
    assert client.get("/api/data/fire-observations", params=params | {"product": "MODIS_NRT"}).json()["total"] == 0
    assert client.get("/api/data/fire-observations", params=params | {"start_date": "2026-01-01", "end_date": "2028-01-01"}).status_code == 422
    assert client.get("/api/earth-fire", params={"bbox": "-180,-90,180,90"}).status_code == 422


def test_cross_origin_write_is_rejected(client):
    result = client.post("/api/compare", json={"experiment_ids": ["a", "b"]}, headers={"Origin": "https://untrusted.example"})
    assert result.status_code == 403


def test_legacy_database_migrates_existing_records(tmp_path, monkeypatch):
    import app.main as main
    path = tmp_path / "legacy.db"
    monkeypatch.setattr(main, "DB_PATH", path)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE analysis_datasets (id TEXT PRIMARY KEY, source_id TEXT, original_filename TEXT, stored_filename TEXT, sha256 TEXT UNIQUE, format TEXT, units TEXT, created_at TEXT, provenance_json TEXT, result_json TEXT)")
        db.execute("INSERT INTO analysis_datasets VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ("old", "user-upload", "old.csv", "old.csv", "a" * 64, "text/csv", "m", "2025-01-01", "{}", "{}"))
        db.execute("CREATE TABLE quantum_experiments (id TEXT PRIMARY KEY, kind TEXT, backend TEXT, seed INTEGER, input_sha256 TEXT, created_at TEXT, result_json TEXT)")
        db.execute("INSERT INTO quantum_experiments VALUES (?,?,?,?,?,?,?)",
                   ("old-q", "circuit", "local", 1, "b" * 64, "2025-01-01", "{}"))
    main.init_db()
    with main.connect() as db:
        assert db.execute("SELECT owner_id FROM analysis_datasets WHERE id='old'").fetchone()[0] == "local"
        assert db.execute("SELECT owner_id FROM quantum_experiments WHERE id='old-q'").fetchone()[0] == "local"


def test_catalog_reads_database_and_does_not_count_unverified_records(client):
    import app.main as main
    with main.connect() as db:
        db.execute("INSERT INTO experiments VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ("LOCAL-UNVERIFIED", "Local test metadata", "Local", "Unknown", "Unknown", "Unknown",
                    "2026-01-01", "user-upload", '{"source":"Local test","source_id":"LOCAL","record":"","finding":"","limits":"Unverified"}', "unverified"))
    items = client.get("/api/experiments").json()
    assert items["total"] == 4
    assert any(item["id"] == "LOCAL-UNVERIFIED" for item in items["items"])
    assert client.get("/api/mission").json()["counts"]["verified_experiment_records"] == 3


def test_simultaneous_identical_uploads_are_idempotent(client, tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path / "uploads")
    raw = ("timestamp,value\n2025-01-01T00:00:00Z,1\n2025-01-01T00:01:00Z,2\n"
           "2025-01-01T00:02:00Z,3\n").encode()
    def upload(_):
        return client.post("/api/datasets/timeseries/analyze", files={"file": ("same.csv", raw, "text/csv")})
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(upload, range(4)))
    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()["dataset_id"] for response in responses}) == 1
    assert client.get("/api/datasets/timeseries").json()["total"] == 1


def test_dataset_quota_rejects_new_file_without_storing_it(client, tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(main, "MAX_DATASETS_PER_OWNER", 1)
    def body(last):
        return ("timestamp,value\n2025-01-01T00:00:00Z,1\n2025-01-01T00:01:00Z,2\n"
                f"2025-01-01T00:02:00Z,{last}\n").encode()
    assert client.post("/api/datasets/timeseries/analyze", files={"file": ("a.csv", body(3), "text/csv")}).status_code == 200
    assert client.post("/api/datasets/timeseries/analyze", files={"file": ("b.csv", body(4), "text/csv")}).status_code == 429
    assert len(list((tmp_path / "uploads").glob("*.csv"))) == 1
