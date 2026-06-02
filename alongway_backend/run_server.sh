#!/bin/bash
# Along-way MVP Backend - Quick Start Script (Linux/Mac)

set -e

echo "=================================="
echo "Along-way MVP Backend Server"
echo "=================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BACKEND_DIR"

echo "📦 Checking dependencies..."
pip install -r requirements.txt > /dev/null 2>&1
echo "✓ Dependencies installed"
echo ""

echo "💾 Initializing database and seeding mock data..."
python -m app.mvp_seed
echo ""

echo "🚀 Starting FastAPI server..."
echo "📖 API docs: http://127.0.0.1:8000/docs"
echo "❤️  Server: http://127.0.0.1:8000/health"
echo ""

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
