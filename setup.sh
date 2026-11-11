#!/bin/bash

# Retail Inventory Forecaster - Setup Script

set -e

echo "======================================"
echo "Retail Inventory Forecaster - Setup"
echo "======================================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { echo "Error: Python 3 is required but not installed."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Error: Node.js is required but not installed."; exit 1; }
command -v psql >/dev/null 2>&1 || { echo "Error: PostgreSQL is required but not installed."; exit 1; }

echo "✓ All prerequisites met"
echo ""

# Database setup
echo "Setting up database..."
read -p "Database name (default: retail_forecaster): " DB_NAME
DB_NAME=${DB_NAME:-retail_forecaster}

read -p "Database user (default: $USER): " DB_USER
DB_USER=${DB_USER:-$USER}

read -sp "Database password: " DB_PASSWORD
echo ""

# Create database
echo "Creating database..."
if ! createdb "$DB_NAME" 2>/tmp/createdb.err; then
    if psql "$DB_NAME" -c "select 1" >/dev/null 2>&1; then
        echo "Database $DB_NAME already exists (or cannot be created by this role); using it"
    else
        cat /tmp/createdb.err
        echo "Could not create or connect to $DB_NAME. Ask a superuser: sudo -u postgres createdb -O $USER $DB_NAME"
        exit 1
    fi
fi

# Initialize schema
echo "Initializing database schema..."
psql $DB_NAME < database/schema.sql

echo "✓ Database setup complete"
echo ""

# Backend setup
echo "Setting up backend..."
cd backend

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
FLASK_ENV=development
FLASK_PORT=5000
# Empty = use all history (right for the synthetic dataset). For Favorita use 2014-04-01.
TRAINING_START_DATE=
EOF

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Generate the seeded synthetic dataset (Favorita-shaped; known promo effect, useless oil price)
echo "Generating sample data..."
python generate_sample_data.py

# Offline rolling-CV evaluation: the API only reads these results
echo "Evaluating forecasts (rolling cross-validation, a minute or two)..."
python -m evaluate --all

echo "✓ Backend setup complete"
cd ..
echo ""

# Frontend setup
echo "Setting up frontend..."
cd frontend

echo "Installing Node dependencies..."
npm install

echo "✓ Frontend setup complete"
cd ..
echo ""

echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "To start the application:"
echo ""
echo "1. Start the backend (in one terminal):"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   python app.py"
echo ""
echo "2. Start the frontend (in another terminal):"
echo "   cd frontend"
echo "   npm start      # Vite dev server on port 3000, proxies /api to :5000"
echo ""
echo "Then open http://localhost:3000 in your browser"
echo ""
