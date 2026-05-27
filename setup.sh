#!/usr/bin/env bash
# setup.sh — Bootstrap POTATO annotation server on a fresh Ubuntu EC2 instance.
#
# Usage:
#   git clone https://github.com/YOUR_ORG/potato-product-category.git
#   cd potato-product-category
#   bash setup.sh
#   bash run.sh          # starts the server on port 8000

set -euo pipefail

echo "=== Installing system dependencies ==="
sudo apt-get update -qq
sudo apt-get install -y python3-pip python3-venv git

echo "=== Creating Python virtual environment ==="
python3 -m venv venv
# shellcheck disable=SC1091
source myenv/bin/activate

echo "=== Installing POTATO ==="
pip install --upgrade pip
pip install potato-annotation

echo ""
echo "=== Setup complete ==="
echo "Run the server with:  bash run.sh"
echo "Then open:            http://$(curl -s http://checkip.amazonaws.com):8000"
