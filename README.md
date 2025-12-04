# Retail Inventory Forecaster

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18.2-61DAFB?style=flat&logo=react&logoColor=black)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12+-4169E1?style=flat&logo=postgresql&logoColor=white)
![Prophet](https://img.shields.io/badge/Prophet-1.1.5-FF6F00?style=flat)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

A full-stack application for forecasting retail inventory using machine learning. The application visualizes forecasts with confidence intervals and historical accuracy metrics.

## Tech Stack

- **Frontend**: ReactJS with Recharts for visualization
- **Backend**: Python + Flask
- **Database**: PostgreSQL (time-series database)
- **ML Model**: Prophet (Facebook's forecasting library)
- **Data Processing**: Pandas

## Features

- ML-powered inventory forecasting using Prophet
- Interactive dashboard with time-series visualization
- 95% confidence intervals for predictions
- Historical accuracy metrics (MAE, MAPE)
- Support for multiple products and categories
- Configurable forecast periods (7-90 days)
- Historical data analysis (30-730 days)

## Prerequisites

- Python 3.8+
- Node.js 14+
- PostgreSQL 12+

## Setup Instructions

### 1. Database Setup

Create a PostgreSQL database:

```bash
createdb retail_forecaster
```

Initialize the database schema:

```bash
cd backend
psql retail_forecaster < ../database/schema.sql
```

### 2. Backend Setup

Create a virtual environment and install dependencies:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Configure environment variables:

```bash
cp .env.example .env
# Edit .env with your database credentials
```

Initialize the database and generate sample data:

```bash
python database.py
python generate_sample_data.py
```

Start the Flask server:

```bash
python app.py
```

The backend API will be available at `http://localhost:5000`

### 3. Frontend Setup

Install dependencies:

```bash
cd frontend
npm install
```

Start the development server:

```bash
npm start
```

The frontend will be available at `http://localhost:3000`

## API Endpoints

- `GET /api/products` - Get list of all products
- `GET /api/historical?product_id=1&days_back=90` - Get historical sales data
- `POST /api/forecast` - Generate forecast for a product
- `GET /api/forecast/:product_id` - Get saved forecast
- `GET /api/accuracy/:product_id` - Get accuracy metrics
- `GET /api/health` - Health check

## Usage

1. Select a product from the dropdown
2. Configure the historical days and forecast period
3. Click "Generate Forecast" to create predictions
4. View the interactive chart with:
   - Blue line: Actual historical sales
   - Purple dashed line: Forecasted sales
   - Shaded area: 95% confidence interval
5. Review accuracy metrics (MAE and MAPE)

## Database Schema

### products
- `product_id` (SERIAL PRIMARY KEY)
- `product_name` (VARCHAR)
- `category` (VARCHAR)
- `unit_price` (DECIMAL)

### sales_data
- `sale_id` (SERIAL PRIMARY KEY)
- `product_id` (FOREIGN KEY)
- `sale_date` (DATE) - indexed for time-series queries
- `quantity_sold` (INTEGER)
- `total_amount` (DECIMAL)

### forecasts
- `forecast_id` (SERIAL PRIMARY KEY)
- `product_id` (FOREIGN KEY)
- `forecast_date` (DATE)
- `predicted_quantity` (DECIMAL)
- `lower_bound` (DECIMAL)
- `upper_bound` (DECIMAL)
- `confidence_level` (DECIMAL)

## Development

### Run Tests

```bash
# Backend tests
cd backend
python -m pytest

# Frontend tests
cd frontend
npm test
```

### Build for Production

```bash
# Build frontend
cd frontend
npm run build

# The build folder will contain optimized production files
```

## Sample Data

The application includes a data generator that creates realistic sample data with:
- 10 sample products across different categories
- 2 years of historical sales data
- Seasonal trends and weekly patterns
- Random variations to simulate real-world data

## Architecture

```
┌─────────────────────────────────────────┐
│  FRONTEND (ReactJS)                     │
│  ├─ Dashboard UI                        │
│  ├─ Recharts visualization              │
│  └─ Product selection controls          │
└────────────────┬────────────────────────┘
                 │ HTTP/REST
                 ▼
┌─────────────────────────────────────────┐
│  BACKEND (Python + Flask)               │
│  ├─ API endpoints                       │
│  ├─ Prophet forecasting model           │
│  └─ Data processing (Pandas)            │
└────────────────┬────────────────────────┘
                 │ SQL
                 ▼
┌─────────────────────────────────────────┐
│  DATABASE (PostgreSQL)                  │
│  ├─ sales_data (time-series)            │
│  ├─ forecasts (predictions)             │
│  └─ products (metadata)                 │
└─────────────────────────────────────────┘
```

## Troubleshooting

### Database Connection Issues

Ensure PostgreSQL is running and the DATABASE_URL in `.env` is correct:

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
psql retail_forecaster
```

### Prophet Installation Issues

Prophet requires additional dependencies. If installation fails:

```bash
# On Ubuntu/Debian
sudo apt-get install python3-dev

# On macOS
brew install gcc

# Then retry
pip install prophet
```

### Port Conflicts

If ports 5000 or 3000 are in use, modify:
- Backend: Change `FLASK_PORT` in `.env`
- Frontend: Set `PORT` environment variable before running `npm start`
