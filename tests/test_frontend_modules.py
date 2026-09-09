from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "narit_vending" / "templates" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "narit_vending" / "static" / "app.js").read_text(encoding="utf-8")
API_CLIENT = (ROOT / "narit_vending" / "static" / "api-client.js").read_text(encoding="utf-8")


def test_api_client_loads_before_application() -> None:
    api_script = "filename='api-client.js'"
    app_script = "filename='app.js'"
    assert TEMPLATE.index(api_script) < TEMPLATE.index(app_script)


def test_application_delegates_transport_to_api_client() -> None:
    assert "window.NaritApiClient.request(path, method, body, timeoutMs)" in APP
    assert "fetch(" not in APP
    assert "window.fetch(path" in API_CLIENT


def test_api_client_preserves_timeout_json_and_backend_error_handling() -> None:
    assert "AbortController" in API_CLIENT
    assert "Controller returned an invalid response" in API_CLIENT
    assert "data.error" in API_CLIENT
    assert "data.reason" in API_CLIENT
    assert "data.message" in API_CLIENT
    assert "window.clearTimeout(timer)" in API_CLIENT


def test_api_client_has_no_machine_or_hardware_authority() -> None:
    forbidden = ("GPIO", "pulse", "motion_enabled", "is_homed", "localStorage")
    for token in forbidden:
        assert token not in API_CLIENT
