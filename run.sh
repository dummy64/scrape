#!/bin/bash
set -e

echo "=== Moglix Scraper Setup ==="

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt --quiet

echo "Installing Playwright browsers..."
playwright install chromium

echo ""
echo "=== Running Scraper ==="
python scraper.py

echo ""
echo "Done! Check the output/ directory for results."
