#!/bin/bash
# FastAPI Development Server Startup Script

set -e

echo "Starting Vocabulary Quiz API..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env file with your configuration before running the API"
fi

# Check if database is running
echo "Checking database connection..."
if docker compose ps | grep -q "vocabulary_quiz.*running"; then
    echo "Database is running"
else
    echo "Starting database..."
    docker compose up -d
    echo "Waiting for database to be ready..."
    sleep 10
fi

# Run the FastAPI application
echo "Starting FastAPI server..."
echo "API will be available at: http://localhost:8000"
echo "API documentation at: http://localhost:8000/docs"
echo "Press Ctrl+C to stop the server"

uvicorn app:app --host 0.0.0.0 --port 8000 --reload
