#!/usr/bin/env bash
# One-shot setup for a fresh Ubuntu VM. Run from the project folder:  bash setup_ubuntu.sh
set -e

echo "==> Installing system packages (needs sudo)"
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv unzip nodejs   # nodejs is optional (CLI --run + extra tests)

echo "==> Versions"
git --version
python3 --version
node --version || true

echo "==> Creating virtual environment and installing Flask"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "==> Running the test-suite"
./venv/bin/python -m unittest discover -s tests

echo
echo "All good. Start the app with:"
echo "    source venv/bin/activate && python app.py"
echo "then open http://127.0.0.1:5000 in the browser."
