#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y python3-gpiozero python3-venv avahi-daemon

sudo hostnamectl set-hostname NaritVendingMachine
sudo systemctl enable --now avahi-daemon

if [ ! -d .venv ]; then
  python3 -m venv --system-site-packages .venv
fi

. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

sudo cp deploy/narit-vending-controller.service /etc/systemd/system/narit-vending-controller.service
sudo cp deploy/narit-vending-web.service /etc/systemd/system/narit-vending-web.service
sudo systemctl daemon-reload

sudo systemctl enable narit-vending-controller.service
sudo systemctl enable narit-vending-web.service

sudo systemctl restart narit-vending-controller.service
sudo systemctl restart narit-vending-web.service

echo "Pi setup complete (2-process architecture: controller + web)."
