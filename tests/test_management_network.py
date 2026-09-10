from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hmi_hostname_setup_is_explicit_and_advertises_http_only():
    script = (ROOT / "scripts" / "configure_hmi_hostname.sh").read_text(encoding="utf-8")
    avahi = (ROOT / "deploy" / "avahi" / "narit-vending-http.service").read_text(encoding="utf-8")
    assert '"${1:-}" != "--apply"' in script
    assert "hostnamectl set-hostname naritvendingmachine" in script
    assert "eth1" not in script
    assert "_http._tcp" in avahi
    assert "<port>80</port>" in avahi


def test_management_network_document_preserves_ot_isolation():
    document = (ROOT / "docs" / "MANAGEMENT_NETWORK_TH.md").read_text(encoding="utf-8")
    assert "http://naritvendingmachine.local/" in document
    assert "eth0" in document and "DHCP" in document
    assert "eth1" in document and "ไม่มี default gateway" in document
    assert "ห้าม bridge" in document
