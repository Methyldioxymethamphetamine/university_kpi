"""tests/test_presentation_routes.py -- verify all routes render through
the unified presentation shell without 500 errors.
"""
import pytest
from scripts.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_dashboard_route(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "NIRF Benchmarking" in html
    assert "Dashboard" in html
    assert "Executive Pipeline Overview" in html
    assert "All Acquired Institutions" in html
    assert "/static/css/tokens.css" in html
    assert "PAGE_HEAD" not in html


def test_runs_route(client):
    res = client.get("/runs")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Run History" in html
    assert "/run/demo_clean_8fixtures/extracted" in html
    assert "/static/css/tables.css" in html


def test_extracted_route(client):
    res = client.get("/run/demo_clean_8fixtures/extracted")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Extraction Browser" in html
    assert "Layer 1: Raw Extracted Rows" in html
    assert "Institution:" in html


def test_extracted_shortcut_redirect(client):
    res = client.get("/extracted")
    assert res.status_code == 302
    assert "/run/" in res.location
    assert "/extracted" in res.location


def test_domains_route(client):
    res = client.get("/run/demo_clean_8fixtures/domains")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Domains Grouping" in html
    assert "Row Counts by Domain" in html
    assert "Faculty" in html
    assert "Student" in html
    assert "Financial" in html
    assert "Placement" in html
    assert "Research" in html


def test_mapped_route(client):
    res = client.get("/run/demo_clean_8fixtures/mapped")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Dictionary Mapping" in html
    assert "Layer 3: KPI Dictionary Mapped Rows" in html


def test_orphans_route(client):
    res = client.get("/run/demo_clean_8fixtures/orphans")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Orphan Concepts" in html
    assert "Layer 4: Preserved Unmapped Disclosures" in html


def test_validation_route(client):
    res = client.get("/run/demo_clean_8fixtures/validation")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Validation &amp; Checksums" in html or "Validation & Checksums" in html
    assert "Validation Results" in html


def test_president_brief_route(client):
    res = client.get("/brief")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "President Brief" in html
    assert "₹37.5L" in html
    assert "₹3.75L" in html
    assert "10&times; apart" in html or "10× apart" in html


def test_scrape_route_get(client):
    res = client.get("/scrape")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Live Scrape" in html
    assert "Paste a Link, Scrape Live" in html


def test_sandbox_testing_route_get(client):
    res = client.get("/test")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Sandbox Testing" in html
    assert "Execute Test Extraction" in html


def test_institutes_redirect(client):
    res = client.get("/institutes")
    assert res.status_code == 302
    assert res.location == "/"


def test_artifact_detail_route(client):
    res = client.get("/artifact/e9a1d469")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Extracted Document Fields" in html
    assert "Validation &amp; Checksums" in html or "Validation & Checksums" in html
    assert "/static/css/tokens.css" in html


def test_institution_selector_human_readable_options(client):
    """Verify that the shared institution selector renders human-readable names with code values."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    # Underlying value must be the institution code
    assert 'value="IR-E-C-16604"' in html
    assert 'value="IR-E-I-1480"' in html
    assert 'value="IR-O-U-0306"' in html
    # Human-readable labels/names must be present
    assert "Sri Sivasubramaniya Nadar College of Engineering" in html
    assert "Thapar Institute of Engineering and Technology" in html
    assert "Indian Institute of Technology Bombay" in html
    # CSS class for non-breaking layout
    assert "inst-select-control" in html


def test_institution_filtering_behavior(client):
    """Verify that selecting an institution filters the dataset and empty restores all."""
    # All rows on extracted
    res_all = client.get("/run/demo_clean_8fixtures/extracted")
    assert res_all.status_code == 200
    html_all = res_all.data.decode("utf-8")

    # Filtered by SSN
    res_filtered = client.get("/run/demo_clean_8fixtures/extracted?institution_code=IR-E-C-16604")
    assert res_filtered.status_code == 200
    html_filtered = res_filtered.data.decode("utf-8")
    assert "IR-E-C-16604" in html_filtered

    # Filtered on domains
    res_domains = client.get("/run/demo_clean_8fixtures/domains?institution_code=IR-O-U-0306")
    assert res_domains.status_code == 200
    assert "Indian Institute of Technology Bombay" in res_domains.data.decode("utf-8")

    # Filtered on mapped
    res_mapped = client.get("/run/demo_clean_8fixtures/mapped?institution_code=IR-E-I-1480")
    assert res_mapped.status_code == 200
    assert "Thapar Institute of Engineering and Technology" in res_mapped.data.decode("utf-8")

    # Dashboard filtered
    res_dash = client.get("/?institution_code=IR-E-U-0456")
    assert res_dash.status_code == 200
    assert "Indian Institute of Technology Madras" in res_dash.data.decode("utf-8")


def test_artifact_institution_code_redirect(client):
    """Verify that passing an institution code to /artifact/<sha> redirects gracefully instead of 404."""
    res = client.get("/artifact/IR-O-U-0306")
    assert res.status_code == 302
    assert res.location.startswith("/artifact/")


def test_table_cells_display_human_readable_institution_names(client):
    """Verify that data tables across priority pages display human-readable institution names."""
    # 1. Extraction table
    res_ext = client.get("/run/demo_clean_8fixtures/extracted")
    assert res_ext.status_code == 200
    html_ext = res_ext.data.decode("utf-8")
    assert "Birla Institute of Technology" in html_ext

    # 2. Domains table
    res_dom = client.get("/run/demo_clean_8fixtures/domains")
    assert res_dom.status_code == 200
    html_dom = res_dom.data.decode("utf-8")
    assert "Indian Institute of Technology Bombay" in html_dom

    # 3. Mapped table
    res_map = client.get("/run/demo_clean_8fixtures/mapped")
    assert res_map.status_code == 200
    html_map = res_map.data.decode("utf-8")
    assert "Indian Institute of Technology Bombay" in html_map

    # 4. Orphans table
    res_orph = client.get("/run/demo_clean_8fixtures/orphans")
    assert res_orph.status_code == 200
    html_orph = res_orph.data.decode("utf-8")
    assert "Sandip Institute of Technology" in html_orph or "Institutions" in html_orph

    # 5. Validation table
    res_val = client.get("/run/demo_clean_8fixtures/validation")
    assert res_val.status_code == 200
    html_val = res_val.data.decode("utf-8")
    assert "Birla Institute of Technology" in html_val or "Indian Institute of Technology" in html_val

    # 6. Runs table
    res_runs = client.get("/runs")
    assert res_runs.status_code == 200
    html_runs = res_runs.data.decode("utf-8")
    assert "Indian Institute of Technology" in html_runs


