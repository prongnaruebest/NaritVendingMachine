from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "Motion_NaritVending" / "Motion_NaritVending"


def test_g491_project_and_protocol_identity_are_consistent() -> None:
    project = (PROJECT / ".cproject").read_text(encoding="utf-8")
    serial = (PROJECT / "Core" / "Src" / "nucleo_serial_link.c").read_text(
        encoding="utf-8"
    )

    assert "STM32G491RETx" in project
    assert "NUCLEO-G491RE" in serial
    assert "NUCLEO_PROTOCOL_VERSION 3U" in serial
    assert "LPUART1" in (PROJECT / "Motion_NaritVending.ioc").read_text(
        encoding="utf-8"
    )


def test_g491_motion_mapping_and_fail_safe_contract() -> None:
    motion = (PROJECT / "Core" / "Src" / "nucleo_motion.c").read_text(
        encoding="utf-8"
    )
    main = (PROJECT / "Core" / "Src" / "main.c").read_text(encoding="utf-8")

    assert "GPIO_PIN_8" in motion and "GPIO_AF6_TIM1" in motion
    assert "GPIO_PIN_9" in motion and "TIM_CHANNEL_2" in motion
    assert "GPIO_PIN_5" in motion and "GPIO_AF1_TIM2" in motion
    assert "GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2" in motion
    assert "NUCLEO_MOTION_WATCHDOG_MS 500U" in (
        PROJECT / "Core" / "Inc" / "nucleo_motion.h"
    ).read_text(encoding="utf-8")
    assert main.index("NucleoMotion_Init();") < main.index("MX_LPUART1_UART_Init();")
    assert "NucleoMotion_Disarm();" in motion
    assert "NucleoMotion_StopAll();" in motion


def test_g491_ioc_records_motion_pins() -> None:
    ioc = (PROJECT / "Motion_NaritVending.ioc").read_text(encoding="utf-8")

    expected = {
        "PA8.Signal=S_TIM1_CH1",
        "PA9.Signal=S_TIM1_CH2",
        "PA5.Signal=S_TIM2_CH1",
        "PB0.GPIO_Label=X_DIR",
        "PB1.GPIO_Label=Y_DIR",
        "PB2.GPIO_Label=Z_DIR",
    }
    assert expected.issubset(set(ioc.splitlines()))


def test_iriv_profile_uses_enumerated_g491_stlink_v3_serial_path() -> None:
    """Keep the deployed path aligned with Linux's stable STLINK-V3 udev name."""
    import json

    hardware = json.loads(
        (ROOT / "hardware_config.iriv.json").read_text(encoding="utf-8")
    )

    assert hardware["nucleo"]["port"] == (
        "/dev/serial/by-id/"
        "usb-STMicroelectronics_STLINK-V3_001C00303433510237363934-if02"
    )
