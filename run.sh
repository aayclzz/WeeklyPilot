#!/bin/bash
# WeeklyPilot - Cross-platform launcher for macOS/Linux
# Usage: ./run.sh [mode] [args]

set -e

echo ""
echo "========================================"
echo "  WeeklyPilot - LanQiao Weekly Report System V4.1"
echo "========================================"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Find Python
PYTHON=""
if command -v python3 &> /dev/null; then
    PYTHON="python3"
elif command -v python &> /dev/null; then
    PYTHON="python"
else
    echo "[ERROR] Python not found. Please install Python 3.8+"
    echo "        Download: https://www.python.org/downloads/"
    exit 1
fi

echo "[INFO] Found Python: $PYTHON"

# Check Python version
VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
MAJOR=$(echo $VERSION | cut -d. -f1)
MINOR=$(echo $VERSION | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 8 ]); then
    echo "[ERROR] Python version $VERSION is too old. Python 3.8+ is required."
    exit 1
fi

# Create .env if needed
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo ""
    echo "[SETUP] Created .env from .env.example"
    echo "[SETUP] Please edit .env and fill in your account info before running."
    echo "       Required fields: LANQIAO_USERNAME, LANQIAO_PASSWORD, OPENAI_API_KEY"
    echo ""
    
    # Try to open in default editor
    if command -v open &> /dev/null; then
        open .env
    elif command -v xdg-open &> /dev/null; then
        xdg-open .env
    else
        echo "Please edit: $(pwd)/.env"
    fi
    
    read -p "Press Enter to continue..."
    exit 0
fi

# Check and install dependencies
if ! $PYTHON -c "import flask" 2>/dev/null; then
    echo ""
    echo "[SETUP] First run detected, installing dependencies..."
    
    # Try with mirror first (for users in China)
    if $PYTHON -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null; then
        echo "[SETUP] Dependencies installed successfully!"
    else
        echo "[WARN] Install with mirror failed, retrying with default source..."
        if $PYTHON -m pip install -r requirements.txt; then
            echo "[SETUP] Dependencies installed successfully!"
        else
            echo "[ERROR] Failed to install dependencies. Please run manually:"
            echo "       $PYTHON -m pip install -r requirements.txt"
            exit 1
        fi
    fi
fi

# Parse arguments
MODE="${1:-select}"

case "$MODE" in
    help)
        echo ""
        echo "Usage: ./run.sh [mode] [args]"
        echo ""
        echo "Modes:"
        echo "  select       Visual select mode (default)"
        echo "  direct       Direct input mode"
        echo "  catalog ID   View course catalog"
        echo "  test ID      Test mode"
        echo "  clear-cache  Clear cache"
        echo "  help         Show help"
        exit 0
        ;;
    select)
        echo ""
        echo "[MODE] Visual Select Mode"
        echo ""
        $PYTHON main.py --select
        ;;
    direct)
        echo ""
        echo "[MODE] Direct Input Mode"
        echo ""
        $PYTHON main.py --direct
        ;;
    catalog)
        echo ""
        echo "[MODE] View Course Catalog"
        echo ""
        $PYTHON main.py --catalog --course-id "$2"
        ;;
    test)
        echo ""
        echo "[MODE] Test Mode"
        echo ""
        $PYTHON main.py --test --course-id "$2"
        ;;
    clear-cache)
        echo ""
        echo "[MODE] Clear Cache"
        echo ""
        $PYTHON main.py --clear-cache
        ;;
    *)
        echo ""
        echo "[MODE] Visual Select Mode"
        echo ""
        $PYTHON main.py --select
        ;;
esac

echo ""
echo "Done."
