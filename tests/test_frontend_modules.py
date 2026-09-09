from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "narit_vending" / "templates" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "narit_vending" / "static" / "app.js").read_text(encoding="utf-8")
API_CLIENT = (ROOT / "narit_vending" / "static" / "api-client.js").read_text(encoding="utf-8")
MACHINE_STORE = (ROOT / "narit_vending" / "static" / "machine-store.js").read_text(encoding="utf-8")
PAGE_CONTROLLERS = (ROOT / "narit_vending" / "static" / "page-controllers.js").read_text(encoding="utf-8")
IO_PAGE_CONTROLLER = (ROOT / "narit_vending" / "static" / "io-page-controller.js").read_text(encoding="utf-8")
EVENTS_PAGE_CONTROLLER = (ROOT / "narit_vending" / "static" / "events-page-controller.js").read_text(encoding="utf-8")
FLOW_PAGE_CONTROLLER = (ROOT / "narit_vending" / "static" / "flow-page-controller.js").read_text(encoding="utf-8")
MQTT_PAGE_CONTROLLER = (ROOT / "narit_vending" / "static" / "mqtt-page-controller.js").read_text(encoding="utf-8")
ALARMS_PAGE_CONTROLLER = (ROOT / "narit_vending" / "static" / "alarms-page-controller.js").read_text(encoding="utf-8")
SLOTS_PAGE_CONTROLLER = (ROOT / "narit_vending" / "static" / "slots-page-controller.js").read_text(encoding="utf-8")
SELECTED_SLOT_CONTROLLER = (ROOT / "narit_vending" / "static" / "selected-slot-controller.js").read_text(encoding="utf-8")
VISUALIZATION_PAGE_CONTROLLER = (ROOT / "narit_vending" / "static" / "visualization-page-controller.js").read_text(encoding="utf-8")
DEMO_PAGE_CONTROLLER = (ROOT / "narit_vending" / "static" / "demo-page-controller.js").read_text(encoding="utf-8")
IO_REGISTRY_VIEW = (ROOT / "narit_vending" / "static" / "io-registry-view.js").read_text(encoding="utf-8")
SYSTEM_CONTROL_PAGE_CONTROLLER = (ROOT / "narit_vending" / "static" / "system-control-page-controller.js").read_text(encoding="utf-8")
ROUTER = (ROOT / "narit_vending" / "static" / "router.js").read_text(encoding="utf-8")
TOKENS = (ROOT / "narit_vending" / "static" / "tokens.css").read_text(encoding="utf-8")
STYLE = (ROOT / "narit_vending" / "static" / "style.css").read_text(encoding="utf-8")
COMPONENTS = (ROOT / "narit_vending" / "static" / "components.css").read_text(encoding="utf-8")
LAYOUT = (ROOT / "narit_vending" / "static" / "layout.css").read_text(encoding="utf-8")


def test_api_client_loads_before_application() -> None:
    api_script = "filename='api-client.js'"
    app_script = "filename='app.js'"
    assert TEMPLATE.index(api_script) < TEMPLATE.index(app_script)


def test_css_token_layer_loads_before_component_and_page_styles() -> None:
    token_stylesheet = "filename='tokens.css'"
    component_stylesheet = "filename='style.css'"
    reusable_stylesheet = "filename='components.css'"
    layout_stylesheet = "filename='layout.css'"
    assert TEMPLATE.index(token_stylesheet) < TEMPLATE.index(component_stylesheet) < TEMPLATE.index(reusable_stylesheet) < TEMPLATE.index(layout_stylesheet)
    assert ":root" in TOKENS
    assert "--bg:" in TOKENS
    assert "--text:" in TOKENS
    assert "--green:" in TOKENS
    assert "box-sizing: border-box" in TOKENS
    assert ":root" not in STYLE
    assert "UNIFIED RESPONSIVE LAYOUT V2" not in STYLE
    assert "UNIFIED RESPONSIVE LAYOUT V2" in LAYOUT
    assert ".workspace-view.io-status-page.active" in LAYOUT
    assert '@media (max-width: 900px)' in LAYOUT
    assert ".axis-speed-row" not in STYLE
    assert ".axis-speed-row" in COMPONENTS
    assert ".linked-speed-panel" in COMPONENTS


def test_machine_store_loads_between_transport_and_application() -> None:
    api_script = "filename='api-client.js'"
    store_script = "filename='machine-store.js'"
    controllers_script = "filename='page-controllers.js'"
    io_controller_script = "filename='io-page-controller.js'"
    events_controller_script = "filename='events-page-controller.js'"
    flow_controller_script = "filename='flow-page-controller.js'"
    mqtt_controller_script = "filename='mqtt-page-controller.js'"
    alarms_controller_script = "filename='alarms-page-controller.js'"
    slots_controller_script = "filename='slots-page-controller.js'"
    selected_slot_script = "filename='selected-slot-controller.js'"
    visualization_script = "filename='visualization-page-controller.js'"
    demo_script = "filename='demo-page-controller.js'"
    io_registry_script = "filename='io-registry-view.js'"
    system_control_script = "filename='system-control-page-controller.js'"
    app_script = "filename='app.js'"
    router_script = "filename='router.js'"
    assert (
        TEMPLATE.index(api_script)
        < TEMPLATE.index(store_script)
        < TEMPLATE.index(controllers_script)
        < TEMPLATE.index(io_controller_script)
        < TEMPLATE.index(events_controller_script)
        < TEMPLATE.index(flow_controller_script)
        < TEMPLATE.index(mqtt_controller_script)
        < TEMPLATE.index(alarms_controller_script)
        < TEMPLATE.index(slots_controller_script)
        < TEMPLATE.index(selected_slot_script)
        < TEMPLATE.index(visualization_script)
        < TEMPLATE.index(demo_script)
        < TEMPLATE.index(io_registry_script)
        < TEMPLATE.index(system_control_script)
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


def test_visualization_controls_are_owned_by_page_scoped_controller() -> None:
    assert "NaritVisualizationPageController.create" in APP
    assert "const cleanupControls = visualizationControls.mount()" in APP
    assert "cleanupControls()" in APP
    assert 'el("visual-slot-grid").addEventListener' not in APP
    assert 'document.getElementById("visual-slot-grid")' in VISUALIZATION_PAGE_CONTROLLER
    assert "addEventListener(eventName, handler)" in VISUALIZATION_PAGE_CONTROLLER
    assert "removeEventListener(eventName, handler)" in VISUALIZATION_PAGE_CONTROLLER
    for callback in (
        "onSelect: selectVisualizationSlot",
        "onCoordinateInput: updateVisualizationCoordinateDraft",
        "onSave: saveVisualSlotV32",
        "onGoto: gotoVisualSlot",
        "onPreview: previewVisualSlot",
    ):
        assert callback in APP


def test_visualization_controller_has_no_direct_transport_or_machine_authority() -> None:
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope", "POST"):
        assert forbidden not in VISUALIZATION_PAGE_CONTROLLER


def test_demo_controls_share_visualization_page_lifecycle() -> None:
    assert "NaritDemoPageController.create" in APP
    assert "const cleanupDemo = demoControls.mount()" in APP
    assert "cleanupDemo()" in APP
    assert 'el("demo-configure")?.addEventListener' not in APP
    for control_id in ("demo-configure", "demo-start", "demo-stop", "demo-history-refresh", "demo-max-cycles"):
        assert f'document.getElementById("{control_id}")' in DEMO_PAGE_CONTROLLER
    assert "addEventListener(eventName, handler)" in DEMO_PAGE_CONTROLLER
    assert "removeEventListener(eventName, handler)" in DEMO_PAGE_CONTROLLER
    for callback in ("onConfigure:", "onValidate:", "onArm:", "onStart:", "onStop:", "onParametersChanged:"):
        assert callback in APP


def test_demo_controller_has_no_direct_transport_or_machine_authority() -> None:
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope", "POST"):
        assert forbidden not in DEMO_PAGE_CONTROLLER


def test_io_views_delegate_registry_metadata_to_pure_selectors() -> None:
    assert "NaritIORegistryView.channels" in APP
    assert "NaritIORegistryView.first" in APP
    assert "NaritIORegistryView.definition" in APP
    assert "NaritIORegistryView.definitions" in APP
    assert "const IO_KIND_LABELS" not in APP
    for kind in ("safety_interlock", "drive_alarm", "position_feedback", "position_switch", "process_sensor", "command_output"):
        assert kind in IO_REGISTRY_VIEW
    for derived in ("category", "terminal", "coil", "highlight", "isSafety", "isAlarm"):
        assert derived in IO_REGISTRY_VIEW


def test_io_registry_view_is_pure_and_has_no_machine_authority() -> None:
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope", "POST", "document."):
        assert forbidden not in IO_REGISTRY_VIEW


def test_system_control_actions_use_page_scoped_lifecycle() -> None:
    assert 'pageControllers.register("system-control"' in APP
    assert "NaritSystemControlPageController.create" in APP
    assert 'el("system-motion-disable")?.addEventListener' not in APP
    for control_id in (
        "system-motion-disable", "system-motion-enable", "system-nucleo-reset",
        "system-drive-power-reset", "system-drive-power-cut", "system-drive-power-restore",
    ):
        assert control_id in SYSTEM_CONTROL_PAGE_CONTROLLER
    assert 'node?.addEventListener("click", handler)' in SYSTEM_CONTROL_PAGE_CONTROLLER
    assert 'node?.removeEventListener("click", handler)' in SYSTEM_CONTROL_PAGE_CONTROLLER
    for callback in (
        "onDisableMotion:", "onEnableMotion:", "onResetNucleoLink:",
        "onResetDrivePower:", "onCutDrivePower:", "onRestoreDrivePower:",
    ):
        assert callback in APP


def test_system_control_page_controller_has_no_transport_or_hardware_authority() -> None:
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope", "POST"):
        assert forbidden not in SYSTEM_CONTROL_PAGE_CONTROLLER


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


def test_system_flow_interaction_is_page_scoped_and_read_only() -> None:
    assert 'pageControllers.register("flow"' in APP
    assert "NaritFlowPageController.create" in APP
    assert 'removeEventListener("click", onNodeClick)' in FLOW_PAGE_CONTROLLER
    assert "No machine command is sent from this panel" in FLOW_PAGE_CONTROLLER
    assert "replaceChildren" in FLOW_PAGE_CONTROLLER
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope", "POST", "innerHTML"):
        assert forbidden not in FLOW_PAGE_CONTROLLER


def test_mqtt_controls_are_page_scoped_without_moving_global_telemetry() -> None:
    assert 'pageControllers.register("mqtt"' in APP
    assert "NaritMqttPageController.create" in APP
    assert 'removeEventListener("click", connect)' in MQTT_PAGE_CONTROLLER
    assert 'removeEventListener("click", disconnect)' in MQTT_PAGE_CONTROLLER
    assert 'options.control("connect")' in MQTT_PAGE_CONTROLLER
    assert 'options.control("disconnect")' in MQTT_PAGE_CONTROLLER
    assert "const mqttRefresh = refreshMqtt()" in APP
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope"):
        assert forbidden not in MQTT_PAGE_CONTROLLER


def test_alarm_page_reset_is_scoped_and_uses_injected_command_path() -> None:
    assert 'pageControllers.register("alarms"' in APP
    assert "NaritAlarmsPageController.create" in APP
    assert 'removeEventListener("click", onReset)' in ALARMS_PAGE_CONTROLLER
    assert "options.reset()" in ALARMS_PAGE_CONTROLLER
    assert '"/api/clear-alarm"' in APP
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope"):
        assert forbidden not in ALARMS_PAGE_CONTROLLER


def test_slot_table_uses_one_page_scoped_delegated_listener() -> None:
    assert 'pageControllers.register("slots"' in APP
    assert "NaritSlotsPageController.create" in APP
    assert 'table?.addEventListener("click", onTableClick)' in SLOTS_PAGE_CONTROLLER
    assert 'table?.removeEventListener("click", onTableClick)' in SLOTS_PAGE_CONTROLLER
    assert 'table?.addEventListener("input", onCoordinate)' in SLOTS_PAGE_CONTROLLER
    assert "$$('[data-slot-coordinate]')" not in APP
    for action in ("onSave", "onSelect", "onGoto", "onDispense", "onTeach"):
        assert f"options.{action}" in SLOTS_PAGE_CONTROLLER


def test_selected_slot_controls_use_the_motion_page_lifecycle() -> None:
    assert 'pageControllers.register("motion"' in APP
    assert "NaritSelectedSlotController.create" in APP
    for listener in (
        'selected?.addEventListener("change", onSelectedChange)',
        'loadTarget?.addEventListener("click", onLoadTarget)',
        'validate?.addEventListener("click", onValidate)',
        'sequenceToggle?.addEventListener("change", onSequenceToggle)',
        'selectedGoto?.addEventListener("click", onSelectedGoto)',
    ):
        assert listener in SELECTED_SLOT_CONTROLLER
    for callback in (
        "onSelectedChange: changeSelectedSlot",
        "onLoadTarget: loadSelectedSlotTarget",
        "onValidate: validateSelectedSlotTarget",
        "onSequenceToggle: setSlotSequenceMode",
        "onSelectedGoto: gotoSelectedSlot",
    ):
        assert callback in APP
    assert 'el("selected-slot-load-target").click()' not in APP


def test_selected_slot_controller_has_no_direct_transport_or_machine_authority() -> None:
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope", "POST"):
        assert forbidden not in SELECTED_SLOT_CONTROLLER


def test_slots_controller_has_no_direct_transport_or_machine_authority() -> None:
    for forbidden in ("fetch(", "/api/", "GPIO", "CommandEnvelope", "POST"):
        assert forbidden not in SLOTS_PAGE_CONTROLLER
