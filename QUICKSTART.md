# Quick Start Guide

Get the Retail Inventory Forecaster running in minutes.

## Option 1: Docker (one command)

```bash
docker compose up --build
```

This starts Postgres (schema applied on first start), loads the **seeded synthetic dataset**, runs the offline
evaluation, then starts the backend (http://localhost:5000) and frontend (http://localhost:3000).

To use the real Favorita dataset instead (see `KAGGLE_IMPORT_INSTRUCTIONS.md` for the download):

```bash
# CSVs in data/store-sales/. Favorita promotions are unrecorded before 2014-04-01, hence the start date.
TRAINING_START_DATE=2014-04-01 docker compose --profile kaggle up --build
```

## Option 2: Automated local setup

```bash
./setup.sh
```

Creates the database, applies the schema, sets up the backend, generates synthetic data, runs the evaluation and
installs the frontend dependencies.

## Option 3: Manual local setup

```bash
# 1. Database
createdb retail_forecaster     # skip if it already exists. "permission denied"? Ask a superuser:
                               #   sudo -u postgres createdb -O "$USER" retail_forecaster

# 2. Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                               # edit DATABASE_URL; set TRAINING_START_DATE= (empty) for synthetic data
python database.py                                 # apply schema (idempotent; also migrates an older database)
python generate_sample_data.py                     # seeded synthetic dataset
python -m evaluate --all                           # offline evaluation (rolling CV, baselines, ablation)

# 3. Frontend
cd ../frontend
npm install
```

### Run

```bash
# Terminal 1
cd backend && source venv/bin/activate && python app.py     # http://localhost:5000

# Terminal 2
cd frontend && npm start                                    # http://localhost:3000 (Vite; proxies /api)
```

## First use

1. Open http://localhost:3000 and pick a product (for the synthetic data: Beverages, Produce, Dairy, Cleaning).
2. Accuracy and inventory panels load from stored results. Nothing is trained when you select a product.
3. Click **Generate forecast** to train once and store a new 90-day forecast run.
4. Read the chart (forecast, 95% interval, faint seasonal-naive reference), the **Forecast accuracy** panel (model vs.
   baselines per horizon range, with a verdict) and the **Inventory recommendation** panel (enter lead time, service
   level and on-hand stock).

## Tests

```bash
cd backend && pytest -m "not slow"     # fast loop: no Prophet fit
cd backend && pytest                   # all tiers; db tests use a throwaway schema of DATABASE_URL, slow tests fit Prophet
cd frontend && npm test && npm run typecheck
```

## Troubleshooting

- **"Connection refused"**: make sure PostgreSQL is running and `backend/.env` has the right `DATABASE_URL`.
- **"Not evaluated yet" in the accuracy panel**: run `python -m evaluate --all` (or `--product <id>`).
- **Forecast marked out of date**: the product was re-evaluated with a different configuration, or its data changed. Click Regenerate.
- **Port in use**: backend `FLASK_PORT` in `backend/.env`; frontend `npm start -- --port 3001`.
