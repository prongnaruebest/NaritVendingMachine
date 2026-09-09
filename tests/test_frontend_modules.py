from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "narit_vending" / "templates" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "narit_vending" / "static" / "app.js").read_text(encoding="utf-8")
API_CLIENT = (ROOT / "narit_vending" / "static" / "api-client.js").read_text(encoding="utf-8")
MACHINE_STORE = (ROOT / "narit_vending" / "static" / "machine-store.js").read_text(encoding="utf-8")
PAGE_CONTROLLERS = (ROOT / "narit_vending" / "static" / "page-controllers.js").read_text(encoding="utf-8")
IO_PAGE_CONTROLLER = (ROOT / "narit_vending" / "static" / "io-page-controller.js").read_text(encoding="utf-8")
EVENTS_PAGE_CONTROLLER = (ROOT / "narit_vending" / "static" / "events-page-controller.js").read_text(encoding="utf-8")
ROUTER = (ROOT / "narit_vending" / "static" / "router.js").read_text(encoding="utf-8")


def test_api_client_loads_before_application() -> None:
    api_script = "filename='api-client.js'"
    app_script = "filename='app.js'"
    assert TEMPLATE.index(api_script) < TEMPLATE.index(app_script)


def test_machine_store_loads_between_transport_and_application() -> None:
    api_script = "filename='api-client.js'"
    store_script = "filename='machine-store.js'"
    controllers_script = "filename='page-controllers.js'"
    io_controller_script = "filename='io-page-controller.js'"
    events_controller_script = "filename='events-page-controller.js'"
    app_script = "filename='app.js'"
    router_script = "filename='router.js'"
    assert (
        TEMPLATE.index(api_script)
        < TEMPLATE.index(store_script)
        < TEMPLATE.index(controllers_script)
        < TEMPLATE.index(io_controller_script)
        < TEMPLATE.index(events_controller_script)
        < TEMPLATE.index(router_script)
        < TEMPLATE.index(app_script)
    )


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


def test_application_uses_one_shared_machine_store_and_selectors() -> None:
    assert "const MS = window.NaritMachineStore.state" in APP
    assert "const machineSelectors = window.NaritMachineStore.selectors" in APP
    assert "const MS = {" not in APP
    for selector in ("status", "operation", "axis", "allAxesHomed", "motorTest"):
        assert f"{selector}:" in MACHINE_STORE


def test_machine_store_is_browser_state_not_machine_authority() -> None:
    assert "Controller remains machine authority" in MACHINE_STORE
    assert "axisSpeeds: { x: 5.0, y: 5.0, z: 5.0 }" in MACHINE_STORE
    for forbidden in ("fetch(", "GPIO", "CommandEnvelope", "/api/"):
        assert forbidden not in MACHINE_STORE


def test_router_has_idempotent_lifecycle_and_no_machine_authority() -> None:
    assert "if (started) return" in ROUTER
    assert "if (!started) return" in ROUTER
    assert 'removeEventListener("hashchange", onHashChange)' in ROUTER
    assert "beforeNavigate" in ROUTER
    assert "afterNavigate" in ROUTER
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope"):
        assert forbidden not in ROUTER


def test_application_delegates_workspace_navigation_to_router() -> None:
    assert "const workspaceRouter = window.NaritRouter.create" in APP
    assert "return workspaceRouter.navigate(view, updateHash)" in APP
    assert "workspaceRouter.start()" in APP


def test_page_controller_registry_has_bounded_mount_lifecycle() -> None:
    assert "if (activeView === view) return" in PAGE_CONTROLLERS
    assert 'typeof activeCleanup === "function"' in PAGE_CONTROLLERS
    assert "controllers.clear()" in PAGE_CONTROLLERS
    assert "Page controller already registered" in PAGE_CONTROLLERS
    assert 'report(error, "mount", view)' in PAGE_CONTROLLERS
    assert 'report(error, "unmount", previousView)' in PAGE_CONTROLLERS
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope"):
        assert forbidden not in PAGE_CONTROLLERS


def test_visualization_history_polling_is_page_scoped() -> None:
    assert 'pageControllers.register("visualization"' in APP
    assert "window.clearInterval(historyTimer)" in APP
    assert "pageControllers.activate(nextView)" in APP


def test_io_interactions_are_owned_by_page_scoped_controller() -> None:
    assert 'pageControllers.register("io-status"' in APP
    assert "NaritIOPageController.create" in APP
    assert "I/O Status Page event listeners" not in APP
    assert 'removeEventListener("click", onFilter)' in IO_PAGE_CONTROLLER
    assert 'removeEventListener("input", onSearch)' in IO_PAGE_CONTROLLER
    assert 'removeEventListener("click", onRefresh)' in IO_PAGE_CONTROLLER
    assert "options.state.ioFilter" in IO_PAGE_CONTROLLER
    assert "options.state.ioSearch" in IO_PAGE_CONTROLLER


def test_io_page_controller_is_read_only_and_has_no_transport_authority() -> None:
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope", "POST"):
        assert forbidden not in IO_PAGE_CONTROLLER


def test_event_log_interactions_are_owned_by_page_scoped_controller() -> None:
    assert 'pageControllers.register("events"' in APP
    assert "NaritEventsPageController.create" in APP
    assert "Event History filters and read-only detail" not in APP
    for handler in ("onInput", "onClear", "onQuickFilter", "onDetail", "onExport"):
        assert f"{handler}" in EVENTS_PAGE_CONTROLLER
    assert 'removeEventListener("click", onDetail)' in EVENTS_PAGE_CONTROLLER
    assert 'removeEventListener("click", onExport)' in EVENTS_PAGE_CONTROLLER


def test_event_log_controller_is_read_only_and_has_no_transport_authority() -> None:
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope", "POST"):
        assert forbidden not in EVENTS_PAGE_CONTROLLER
