# Kaggle Dataset Import Instructions

## Store Sales - Time Series Forecasting Dataset

This guide walks you through importing real retail sales data from Kaggle into your forecaster.

### Step 1: Get a Kaggle Account

1. Go to https://www.kaggle.com
2. Sign up for a free account (or log in if you have one)

### Step 2: Download the Dataset

**Option A: Web Download (Easier)**
1. Visit: https://www.kaggle.com/competitions/store-sales-time-series-forecasting/data
2. Click the "Download All" button
3. Extract the ZIP file to a folder, e.g., `data/store-sales/`

**Option B: Kaggle CLI (Faster for large datasets)**
```bash
# Install Kaggle CLI
pip install kaggle

# Set up API credentials (see https://www.kaggle.com/docs/api)
# Download ~/.kaggle/kaggle.json from Kaggle website

# Download the dataset
kaggle competitions download -c store-sales-time-series-forecasting

# Extract
unzip store-sales-time-series-forecasting.zip -d data/store-sales/
```

### Step 3: Verify Files

Your `data/store-sales/` directory should contain:
- `train.csv` (main sales data - ~3 million rows)
- `test.csv` (test data)
- `stores.csv` (store information)
- `oil.csv` (oil prices)
- `holidays_events.csv` (Ecuador holidays)
- `sample_submission.csv`

**Required file**: Only `train.csv` is required for the import script.

### Step 4: Run the Import Script

```bash
cd backend
source venv/bin/activate
python import_kaggle_store_sales.py --data-dir ../data/store-sales
```

This will:
1. Clear existing sample data
2. Import 33 product families as products
3. Import ~125,000 aggregated sales records (2013-2017)
4. Take 2-5 minutes depending on your system

### Step 5: Restart Your Backend

```bash
# Stop the current backend (Ctrl+C)
# Restart it
python app.py
```

### Step 6: Test the Forecaster

1. Refresh your browser at http://localhost:3000
2. You'll see real product families like:
   - Grocery I
   - Beverages
   - Home Appliances
   - Personal Care
   - etc.
3. Generate forecasts with 5 years of historical data!

## Dataset Information

### About the Data

- **Source**: Corporación Favorita (major Ecuadorian grocery retailer)
- **Date Range**: January 1, 2013 to August 15, 2017 (4.5+ years)
- **Granularity**: Daily sales
- **Products**: 33 product families (e.g., Produce, Dairy, Beverages, Electronics)
- **Stores**: 54 stores across Ecuador (aggregated in our import)

### What Gets Imported

| Original | Mapped To | Notes |
|----------|-----------|-------|
| Product family (33 types) | products table | Each family becomes a product |
| Daily sales by family | sales_data table | Aggregated across all stores |
| Sales quantity | quantity_sold | Direct mapping |
| Estimated prices | unit_price | Assigned reasonable retail prices |

### Data Quality

- **Complete time series**: No major gaps
- **Strong patterns**: Weekly, monthly, yearly seasonality
- **Holidays**: Ecuador holidays affect sales (included in dataset)
- **Promotions**: On-promotion flags available (not imported yet)

## Expected Results

After import, you should see:
- **Products**: 33 product families
- **Sales records**: ~125,000 rows (aggregated by date and family)
- **MAPE accuracy**: 15-25% (better with more products due to diverse patterns)

## Troubleshooting

### "train.csv not found"
- Make sure you downloaded the dataset
- Check the `--data-dir` path is correct
- Verify the file exists: `ls data/store-sales/train.csv`

### "ModuleNotFoundError: No module named 'pandas'"
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Import takes too long
- The dataset is large (~3M rows)
- Aggregation + import takes 2-5 minutes
- Be patient, it's worth it!

### Database connection error
- Ensure PostgreSQL is running
- Check your `.env` file has correct credentials
- Test: `psql retail_forecaster`

## Next Steps

After successful import:
1. Try forecasting different product families
2. Compare seasonal products (e.g., Celebration vs Beverages)
3. Experiment with different forecast periods (7-90 days)
4. Use different historical windows (90-730 days)

## Reverting to Sample Data

If you want to go back to sample data:
```bash
cd backend
source venv/bin/activate
python -c "from database import get_db_connection; conn = get_db_connection(); cur = conn.cursor(); cur.execute('DELETE FROM forecasts'); cur.execute('DELETE FROM sales_data'); cur.execute('DELETE FROM products'); conn.commit(); cur.close(); conn.close()"
python generate_sample_data.py
```

## Dataset License

This dataset is provided under the Kaggle Competition Data License Agreement. By using this data, you agree to Kaggle's terms of use. This data is for educational and research purposes.
