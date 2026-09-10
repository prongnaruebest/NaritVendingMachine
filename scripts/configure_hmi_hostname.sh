#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "--apply" ]]; then
  echo "This changes the management hostname and may change the SSH address."
  echo "Run: sudo bash scripts/configure_hmi_hostname.sh --apply"
  exit 2
fi

command -v hostnamectl >/dev/null
command -v systemctl >/dev/null
test -f deploy/avahi/narit-vending-http.service

apt-get update
apt-get install -y avahi-daemon libnss-mdns
hostnamectl set-hostname naritvendingmachine
install -m 0644 deploy/avahi/narit-vending-http.service \
  /etc/avahi/services/narit-vending-http.service
systemctl enable --now avahi-daemon
systemctl restart avahi-daemon

echo "HMI hostname configured: http://naritvendingmachine.local/"
echo "Keep the current IP recorded as a maintenance fallback."
