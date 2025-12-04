# Quick Start Guide

Get the Retail Inventory Forecaster running in minutes!

## Option 1: Automated Setup (Recommended)

Run the setup script:

```bash
./setup.sh
```

This will:
- Create the PostgreSQL database
- Initialize the schema
- Set up the backend with sample data
- Install frontend dependencies
- Configure environment variables

## Option 2: Manual Setup

### Step 1: Create Database

```bash
createdb retail_forecaster
psql retail_forecaster < database/schema.sql
```

### Step 2: Setup Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your database credentials

# Generate sample data
python generate_sample_data.py
```

### Step 3: Setup Frontend

```bash
cd frontend
npm install
```

## Running the Application

### Terminal 1 - Start Backend

```bash
cd backend
source venv/bin/activate
python app.py
```

Backend will run on http://localhost:5000

### Terminal 2 - Start Frontend

```bash
cd frontend
npm start
```

Frontend will run on http://localhost:3000

## First Use

1. Open http://localhost:3000 in your browser
2. Select a product from the dropdown (e.g., "Laptop")
3. Keep default settings (90 historical days, 30 forecast days)
4. Click "Generate Forecast"
5. View the interactive chart with:
   - Historical sales (blue line)
   - Forecasted sales (purple dashed line)
   - 95% confidence interval (shaded area)
   - Accuracy metrics (MAE and MAPE)

## Troubleshooting

### "Connection refused" error
- Ensure PostgreSQL is running: `sudo systemctl status postgresql`
- Check database credentials in `backend/.env`

### "Module not found" error
- Activate virtual environment: `source backend/venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### Port already in use
- Backend: Change FLASK_PORT in `backend/.env`
- Frontend: Run `PORT=3001 npm start`

## Sample Products

The application comes pre-loaded with 10 sample products:
- Laptop ($899.99)
- Wireless Mouse ($29.99)
- Office Chair ($199.99)
- Desk Lamp ($49.99)
- Coffee Maker ($79.99)
- Water Bottle ($19.99)
- Notebook Set ($12.99)
- USB Cable ($9.99)
- Backpack ($59.99)
- Desk Organizer ($24.99)

Each has 2 years of simulated sales data with realistic patterns!
