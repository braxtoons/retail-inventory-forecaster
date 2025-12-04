# Database Sources

This document tracks all data sources used in the Retail Inventory Forecaster application.

## Current Data Source

### Sample Generated Data
- **Source**: Internally generated using `backend/generate_sample_data.py`
- **Type**: Synthetic/Mock data
- **Description**: Programmatically generated sales data with realistic seasonal and weekly patterns
- **Date Range**: 2 years of historical data (730 days)
- **Products**: 10 sample products across Electronics, Furniture, Appliances, Accessories, and Stationery categories
- **Records**: ~7,310 sales records (one per product per day)
- **License**: N/A (internal generation)

## Recommended Kaggle Datasets for Real Data

### 1. Store Sales - Time Series Forecasting (RECOMMENDED)
- **Source**: Kaggle Competition
- **Link**: https://www.kaggle.com/competitions/store-sales-time-series-forecasting
- **Provider**: Corporación Favorita (Ecuadorian grocery retailer)
- **Date Range**: 2013-2017 (5+ years)
- **Granularity**: Daily sales data
- **Features**: Multiple products, stores, holidays, promotions
- **Format**: CSV
- **License**: Competition Data License Agreement
- **Why Recommended**: Complete time series, strong seasonal patterns, ideal for Prophet forecasting

### 2. Walmart Sales Forecast
- **Source**: Kaggle Dataset
- **Link**: https://www.kaggle.com/datasets/aslanahmedov/walmart-sales-forecast
- **Provider**: Walmart (via Kaggle user)
- **Granularity**: Weekly sales data
- **Features**: Department-level sales across stores
- **Format**: CSV
- **License**: Check Kaggle dataset page

### 3. Retail Sales Forecasting Dataset
- **Source**: Kaggle Dataset
- **Link**: https://www.kaggle.com/datasets/omkarpkhanvilkar/retail-sales-forecasting-dataset
- **Provider**: Kaggle user omkarpkhanvilkar
- **Last Updated**: May 2024
- **Features**: Structured retail sales data
- **Format**: CSV
- **License**: Check Kaggle dataset page

### 4. Superstore Sales Dataset
- **Source**: Kaggle Dataset
- **Link**: https://www.kaggle.com/datasets/rohitsahoo/sales-forecasting
- **Provider**: Kaggle user rohitsahoo
- **Features**: Superstore sales with product categories
- **Format**: CSV
- **License**: Check Kaggle dataset page

### 5. Store Sales Forecasting Dataset
- **Source**: Kaggle Dataset
- **Link**: https://www.kaggle.com/datasets/tanayatipre/store-sales-forecasting-dataset
- **Provider**: Kaggle user tanayatipre
- **Features**: Time series sales data
- **Format**: CSV
- **License**: Check Kaggle dataset page

### 6. Retail Sales Forecasting (Tevec Systems)
- **Source**: Kaggle Dataset
- **Link**: https://www.kaggle.com/datasets/tevecsystems/retail-sales-forecasting
- **Provider**: Tevec Systems
- **Features**: Retail sales data
- **Format**: CSV
- **License**: Check Kaggle dataset page

## Data Import Instructions

### Store Sales - Time Series Forecasting Dataset

**Import Script**: `backend/import_kaggle_store_sales.py`

**Detailed Instructions**: See `KAGGLE_IMPORT_INSTRUCTIONS.md`

**Quick Start**:
1. Download dataset from Kaggle
2. Extract to `data/store-sales/` directory
3. Run: `python backend/import_kaggle_store_sales.py --data-dir data/store-sales`

### Other Datasets

To import other Kaggle datasets:
1. Download the dataset from Kaggle (requires Kaggle account)
2. Extract CSV files to a local directory
3. Create or adapt import script based on dataset structure
4. Verify data integrity and date ranges
5. Update this file with the active data source

## Active Data Source

**Current**: Sample Generated Data (as of 2025-12-03)

**To Switch to Real Data**: Follow import instructions and update this section with:
- Dataset name
- Import date
- Date range of data
- Number of records imported
- Any data quality notes
