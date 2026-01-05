@echo off
REM ============================================================================
REM Finox Scraper - Windows Setup Script
REM ============================================================================
REM This script sets up the complete development environment
REM ============================================================================

echo ============================================================================
echo Finox Stock Scraper - Setup
echo ============================================================================
echo.

REM Check Python installation
echo [1/6] Checking Python installation...
py --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python 3.11 or higher.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)
py --version
echo.

REM Create virtual environment
echo [2/6] Creating virtual environment...
if exist venv (
    echo Virtual environment already exists, skipping...
) else (
    py -m venv venv
    echo Virtual environment created successfully
)
echo.

REM Activate virtual environment and install dependencies
echo [3/6] Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.

REM Create .env file
echo [4/6] Setting up environment variables...
if exist .env (
    echo .env file already exists, skipping...
) else (
    copy .env.example .env
    echo .env file created from template
    echo IMPORTANT: Edit .env file with your database credentials!
)
echo.

REM Create necessary directories
echo [5/6] Creating data directories...
if not exist logs mkdir logs
if not exist data mkdir data
if not exist data\raw mkdir data\raw
if not exist data\processed mkdir data\processed
if not exist data\backups mkdir data\backups
if not exist data\cache mkdir data\cache
if not exist data\checkpoints mkdir data\checkpoints
echo Data directories created
echo.

REM Test installation
echo [6/6] Testing installation...
python main.py --mode test
echo.

echo ============================================================================
echo Setup completed successfully!
echo ============================================================================
echo.
echo Next steps:
echo 1. Edit .env file with your database credentials
echo 2. Install and configure MySQL database
echo 3. Run: python scripts/init_db.py (when implemented)
echo 4. Run: python main.py --mode scraper
echo.
echo For help: python main.py --help
echo ============================================================================
pause
