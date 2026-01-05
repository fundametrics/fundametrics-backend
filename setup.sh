#!/bin/bash
# ============================================================================
# Finox Scraper - Linux/Mac Setup Script
# ============================================================================
# This script sets up the complete development environment
# ============================================================================

set -e  # Exit on error

echo "============================================================================"
echo "Finox Stock Scraper - Setup"
echo "============================================================================"
echo ""

# Check Python installation
echo "[1/6] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found! Please install Python 3.11 or higher."
    exit 1
fi
python3 --version
echo ""

# Create virtual environment
echo "[2/6] Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists, skipping..."
else
    python3 -m venv venv
    echo "Virtual environment created successfully"
fi
echo ""

# Activate virtual environment and install dependencies
echo "[3/6] Installing dependencies..."
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo ""

# Create .env file
echo "[4/6] Setting up environment variables..."
if [ -f ".env" ]; then
    echo ".env file already exists, skipping..."
else
    cp .env.example .env
    echo ".env file created from template"
    echo "IMPORTANT: Edit .env file with your database credentials!"
fi
echo ""

# Create necessary directories
echo "[5/6] Creating data directories..."
mkdir -p logs
mkdir -p data/raw
mkdir -p data/processed
mkdir -p data/backups
mkdir -p data/cache
mkdir -p data/checkpoints
echo "Data directories created"
echo ""

# Test installation
echo "[6/6] Testing installation..."
python main.py --mode test
echo ""

echo "============================================================================"
echo "Setup completed successfully!"
echo "============================================================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your database credentials"
echo "2. Install and configure MySQL database"
echo "3. Run: python scripts/init_db.py (when implemented)"
echo "4. Run: python main.py --mode scraper"
echo ""
echo "For help: python main.py --help"
echo "============================================================================"
